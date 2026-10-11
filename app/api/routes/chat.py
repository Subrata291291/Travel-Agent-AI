from fastapi import APIRouter, Depends
import logging
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.graph import TravelAgentGraph
from app.auth.dependencies import get_current_user
from app.core.tenant_context import TenantContext
from app.database.connection import describe_database_session, get_db


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)
logger = logging.getLogger(__name__)


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


# One graph instance for the API process.
travel_agent_graph = TravelAgentGraph()


@router.post(
    "",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    context: TenantContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a message to the Travel Agent.

    Authentication:
        JWT
            ↓
        get_current_user()
            ↓
        TenantContext
            ↓
        TravelAgentGraph

    The route does not trust user_id or tenant_id
    supplied by the client.

    Both identities come from the validated JWT.
    """

    logger.info("Chat persistence database session: %s", describe_database_session(db))
    result = travel_agent_graph.run(
        user_message=request.message,
        user_id=context.user_id,
        session_id=request.session_id,
        tenant_id=context.tenant_id,
        db=db,
    )

    booking = result.get("booking")

    booking_domain = (
        result.get("pending_booking_domain")
        or (
            "hotel"
            if isinstance(booking, dict)
            and booking.get("hotel_id")
            else None
        )
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

        booking=booking,

        booking_domain=booking_domain,
    )
