from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.graph import TravelAgentGraph
from app.api.dependencies import get_tenant_context
from app.core.tenant_context import TenantContext


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


class ChatRequest(BaseModel):
    """
    Request body sent by the client.
    """

    message: str = Field(
        ...,
        min_length=1,
        description="User's travel-related message.",
    )

    session_id: str = Field(
        ...,
        min_length=1,
        description="Conversation/session identifier.",
    )


class ChatResponse(BaseModel):
    """
    Standard API response returned by the chat endpoint.
    """

    answer: str | None = None
    session_id: str
    user_id: str
    tenant_id: str

    perception: object | None = None
    plan: object | None = None

    clarification_needed: bool = False
    pending_clarification: str | None = None

    pending_destination: str | None = None

    transport_options: list[dict] = []
    hotel_options: list[dict] = []

    selected_option_id: str | None = None

    pending_booking_confirmation: bool = False
    pending_booking_domain: str | None = None

    booking: dict | None = None

    booking_domain: str | None = None


# Create one graph instance for the API process.
#
# Later, depending on deployment architecture,
# this can be moved into application lifespan/startup
# or a dependency/container.
travel_agent_graph = TravelAgentGraph()


@router.post(
    "",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    context: TenantContext = Depends(get_tenant_context),
):
    """
    Send a message to the Travel Agent.

    The route itself does not contain travel/business logic.
    It delegates the conversation to TravelAgentGraph.
    """

    result = travel_agent_graph.run(
        user_message=request.message,
        user_id=context.user_id,
        session_id=request.session_id,
        tenant_id=context.tenant_id,
    )

    return ChatResponse(
        answer=result.get("answer"),
        session_id=request.session_id,
        user_id=context.user_id,
        tenant_id=context.tenant_id,

        perception=result.get("perception"),
        plan=result.get("plan"),

        clarification_needed=(
            result.get("clarification_needed", False)
            or result.get("pending_clarification") is not None
        ),

        pending_clarification=result.get(
            "pending_clarification",
        ),

        pending_destination=result.get(
            "pending_destination",
        ),

        transport_options=result.get(
            "transport_options",
            [],
        ),

        hotel_options=result.get(
            "hotel_options",
            [],
        ),

        selected_option_id=result.get(
            "selected_option_id",
        ),

        pending_booking_confirmation=result.get(
            "pending_booking_confirmation",
            False,
        ),

        pending_booking_domain=result.get(
            "pending_booking_domain",
        ),

        booking=result.get("booking"),

        booking_domain=(
            result.get("pending_booking_domain")
            or (
                "hotel"
                if result.get("booking", {}).get("hotel_id")
                else None
            )
        ),
    )