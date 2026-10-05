from typing import Annotated, TypedDict
import json

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from app.agents.perception import PerceptionAgent
from app.agents.planner import PlannerAgent
from app.agents.executor import ToolExecutor

from app.llm.router import LLMRouter

from app.memory.conversation import ConversationMemory

from app.tools import get_all_tools
from app.tools.destination_resolver import DestinationResolver

from app.schemas.tool import ToolContext
from app.schemas.booking import BookingRequest

from app.services.booking_service import BookingService


# ============================================================
# STATE
# ============================================================

class TravelState(TypedDict):
    """
    Shared state passed through every LangGraph node.

    This state contains both current-turn information and
    important multi-turn workflow information.

    Important booking fields:

    - transport_options
    - selected_option_id
    - pending_booking_confirmation
    - booking
    """

    user_message: str
    user_id: str
    session_id: str

    messages: Annotated[
        list[BaseMessage],
        add_messages,
    ]

    perception: object | None
    plan: object | None

    destination_resolution: dict | None

    clarification_needed: bool
    pending_clarification: str | None
    pending_destination: str | None

    tool_context: ToolContext | None

    # Transport options discovered in previous turns.
    transport_options: list[dict]

    # Selected option, for example TRAIN-1.
    selected_option_id: str | None

    # True when application is waiting for explicit
    # booking confirmation.
    pending_booking_confirmation: bool

    # Final booking information after successful booking.
    booking: dict | None


# ============================================================
# TRAVEL AGENT GRAPH
# ============================================================

class TravelAgentGraph:
    """
    Main LangGraph orchestration layer.

    Responsibilities:

    - Perception
    - Destination resolution
    - Planning
    - Tool execution
    - Multi-turn transport selection
    - Explicit booking confirmation
    - Deterministic booking execution

    IMPORTANT:

    The LLM never directly performs a booking.

    Booking execution is controlled by application state.
    """

    def __init__(self):

        # ----------------------------------------------------
        # Core components
        # ----------------------------------------------------

        self.router = LLMRouter()

        self.perception_agent = PerceptionAgent(
            self.router
        )

        self.planner_agent = PlannerAgent(
            self.router
        )

        self.tool_executor = ToolExecutor()

        self.memory = ConversationMemory()

        self.destination_resolver = DestinationResolver()

        # These are normal travel/search tools.
        #
        # IMPORTANT:
        # book_transport is NOT part of this list.
        self.tools = get_all_tools()

        # ----------------------------------------------------
        # Booking service
        # ----------------------------------------------------

        self.booking_service = BookingService()

        # ----------------------------------------------------
        # Build graph
        # ----------------------------------------------------

        self.graph = self._build_graph()

    # ========================================================
    # BUILD GRAPH
    # ========================================================

    def _build_graph(self):
        """
        Build and compile the LangGraph workflow.
        """

        graph = StateGraph(TravelState)

        # ----------------------------------------------------
        # Register nodes
        # ----------------------------------------------------

        graph.add_node(
            "perception",
            self.perception_node,
        )

        graph.add_node(
            "planner",
            self.planner_node,
        )

        graph.add_node(
            "destination_resolver",
            self.destination_resolver_node,
        )

        graph.add_node(
            "clarification",
            self.clarification_node,
        )

        graph.add_node(
            "booking_confirmation",
            self.booking_confirmation_node,
        )

        graph.add_node(
            "booking_already_exists",
            self.booking_already_exists_node,
        )

        graph.add_node(
            "get_bookings",
            self.get_bookings_node,
        )

        # NEW:
        # Executes booking only after explicit confirmation.
        graph.add_node(
            "booking_execution",
            self.booking_execution_node,
        )

        # NEW:
        # Handles explicit booking rejection.
        graph.add_node(
            "booking_cancel",
            self.booking_cancel_node,
        )

        # NEW:
        # Handles ambiguous confirmation.
        graph.add_node(
            "booking_waiting",
            self.booking_waiting_node,
        )

        graph.add_node(
            "agent",
            self.agent_node,
        )

        graph.add_node(
            "tools",
            self.tools_node,
        )

        # ----------------------------------------------------
        # START → PERCEPTION
        # ----------------------------------------------------

        graph.add_edge(
            START,
            "perception",
        )

        # ----------------------------------------------------
        # PERCEPTION ROUTING
        # ----------------------------------------------------

        graph.add_conditional_edges(
            "perception",
            self.perception_route,
            {
                "new_booking": "booking_confirmation",
                "execute_booking": "booking_execution",
                "cancel_booking": "booking_cancel",
                "wait_booking": "booking_waiting",
                "destination": "destination_resolver",
                "booking_already_exists": "booking_already_exists",
                "get_bookings": "get_bookings",
            },
        )

        # ----------------------------------------------------
        # DESTINATION ROUTING
        # ----------------------------------------------------

        graph.add_conditional_edges(
            "destination_resolver",
            self.destination_route,
            {
                "planner": "planner",
                "clarification": "clarification",
            },
        )

        # ----------------------------------------------------
        # PLANNER → AGENT
        # ----------------------------------------------------

        graph.add_edge(
            "planner",
            "agent",
        )

        # ----------------------------------------------------
        # CLARIFICATION → END
        # ----------------------------------------------------

        graph.add_edge(
            "clarification",
            END,
        )

        # ----------------------------------------------------
        # BOOKING CONFIRMATION → END
        #
        # This node only asks:
        #
        # "Do you want me to book this?"
        #
        # It does NOT perform booking.
        # ----------------------------------------------------

        graph.add_edge(
            "booking_confirmation",
            END,
        )

        # ----------------------------------------------------
        # BOOKING EXECUTION → END
        # ----------------------------------------------------

        graph.add_edge(
            "booking_execution",
            END,
        )

        # ----------------------------------------------------
        # BOOKING CANCEL → END
        # ----------------------------------------------------

        graph.add_edge(
            "booking_cancel",
            END,
        )

        # ----------------------------------------------------
        # BOOKING WAITING → END
        # ----------------------------------------------------

        graph.add_edge(
            "booking_waiting",
            END,
        )

        # ----------------------------------------------------
        # AGENT → TOOLS / END
        # ----------------------------------------------------

        graph.add_conditional_edges(
            "agent",
            self.should_use_tools,
            {
                "tools": "tools",
                "end": END,
            },
        )

        # ----------------------------------------------------
        # Booking Already Exists → TOOLS / END
        # ----------------------------------------------------
        graph.add_edge(
            "booking_already_exists",
            END,
        )

        # ----------------------------------------------------
        # GET BOOKINGS → END
        # ----------------------------------------------------
        graph.add_edge(
            "get_bookings",
            END,
        )

        # ----------------------------------------------------
        # TOOLS → AGENT
        # ----------------------------------------------------

        graph.add_edge(
            "tools",
            "agent",
        )

        return graph.compile()

    # ========================================================
    # NODE 1 — PERCEPTION
    # ========================================================

    def perception_node(
        self,
        state: TravelState,
    ):
        """
        Understand the current user message.
        """

        conversation_history = self.memory.get_messages(
            state["session_id"]
        )

        perception = self.perception_agent.understand(
            state["user_message"],
            conversation_history,
        )

        return {
            "perception": perception,
        }

    # ========================================================
    # NODE 2 — PLANNER
    # ========================================================

    def planner_node(
        self,
        state: TravelState,
    ):
        """
        Convert perception into an executable travel plan.
        """

        memory_context = self.memory.get_context(
            state["session_id"],
            state["user_id"],
        )

        memory_context["resolved_destination"] = (
            state["destination_resolution"]
        )

        plan = self.planner_agent.create_plan(
            state["perception"],
            memory_context,
        )

        return {
            "plan": plan,
        }

    # ========================================================
    # NODE 3 — DESTINATION RESOLVER
    # ========================================================

    def destination_resolver_node(
        self,
        state: TravelState,
    ):
        """
        Resolve the user's destination.
        """

        perception = state["perception"]

        destination = perception.destination

        pending_clarification = state.get(
            "pending_clarification"
        )

        pending_destination = state.get(
            "pending_destination"
        )

        # ----------------------------------------------------
        # Handle previous clarification
        #
        # Example:
        #
        # Previous:
        # "Which Manali?"
        #
        # Current:
        # "Himachal Pradesh"
        #
        # Result:
        # "Manali, Himachal Pradesh"
        # ----------------------------------------------------

        if (
            pending_clarification == "destination"
            and pending_destination
            and destination
        ):

            normalized_destination = (
                destination.strip().lower()
            )

            normalized_pending = (
                pending_destination.strip().lower()
            )

            if (
                normalized_destination
                != normalized_pending
                and not normalized_destination.startswith(
                    f"{normalized_pending},"
                )
            ):
                destination = (
                    f"{pending_destination}, "
                    f"{destination}"
                )

        # ----------------------------------------------------
        # Some requests do not require destination.
        # ----------------------------------------------------

        if not destination:
            return {
                "destination_resolution": {
                    "status": "not_required"
                },
                "clarification_needed": False,
            }

        # ----------------------------------------------------
        # Resolve destination
        # ----------------------------------------------------

        result = self.destination_resolver.resolve(
            destination
        )

        # ----------------------------------------------------
        # Successfully resolved
        # ----------------------------------------------------

        if result["status"] == "resolved":

            return {
                "destination_resolution": result,
                "clarification_needed": False,
                "pending_clarification": None,
                "pending_destination": None,
                "tool_context": None,
            }

        # ----------------------------------------------------
        # Ambiguous / unresolved
        # ----------------------------------------------------

        return {
            "destination_resolution": result,
            "clarification_needed": True,
            "pending_clarification": "destination",
            "pending_destination": destination,
        }

    # ========================================================
    # ROUTER — PERCEPTION
    # ========================================================

    def perception_route(self, state: TravelState):
        """
        Decide what happens after perception.

        Booking routing is deterministic.

        Priority:
        1. Already confirmed booking
        2. Pending booking confirmation
        3. New booking request
        4. Normal travel flow
        """

        perception = state.get("perception")

        if not perception:
            return "destination"

        # ====================================================
        # CASE 1 — BOOKING ALREADY EXISTS
        # ====================================================
        #
        # If this session already has a confirmed booking,
        # do NOT start another booking flow.
        #
        # Example:
        #
        # Turn 4:
        #   Yes, book it
        #
        # Turn 5:
        #   Yes, book it
        #
        # Turn 5 must NOT create another booking.
        # ====================================================

        existing_booking = state.get("booking")

        if existing_booking:

            confirmation = getattr(
                perception,
                "confirmation",
                "unknown",
            )

            intent = getattr(
                perception,
                "intent",
                None,
            )

            if (
                confirmation == "yes"
                or intent == "book_trip"
            ):
                return "booking_already_exists"

        # ====================================================
        # CASE 2 — PENDING BOOKING
        # ====================================================

        pending_booking = state.get(
            "pending_booking_confirmation",
            False,
        )

        if pending_booking:

            confirmation = getattr(
                perception,
                "confirmation",
                "unknown",
            )

            if confirmation == "yes":
                return "execute_booking"

            if confirmation == "no":
                return "cancel_booking"

            return "wait_booking"

        # ====================================================
        # CASE 3 — GET USER BOOKINGS
        # ====================================================

        if perception.intent == "get_bookings":
            return "get_bookings"


        # ====================================================
        # CASE 4 — NEW BOOKING REQUEST
        # ====================================================

        if (
            perception.intent == "book_trip"
            and perception.selected_option_id
        ):
            return "new_booking"


        # ====================================================
        # CASE 5 — NORMAL TRAVEL FLOW
        # ====================================================

        return "destination"

    # ========================================================
    # ROUTER — DESTINATION
    # ========================================================

    def destination_route(
        self,
        state: TravelState,
    ):
        """
        Decide whether destination clarification is required.
        """

        if state["clarification_needed"]:
            return "clarification"

        return "planner"

    # ========================================================
    # NODE 4 — CLARIFICATION
    # ========================================================

    def clarification_node(
        self,
        state: TravelState,
    ):
        """
        Ask the user to clarify an ambiguous destination.
        """

        resolution = state["destination_resolution"]

        candidates = resolution.get(
            "candidates",
            [],
        )

        # ----------------------------------------------------
        # Remove duplicate locations
        # ----------------------------------------------------

        unique_candidates = []

        seen_locations = set()

        for candidate in candidates:

            name = candidate.get("name")
            region = candidate.get("admin1")
            country = candidate.get("country")

            location_key = (
                name,
                region,
                country,
            )

            if location_key in seen_locations:
                continue

            seen_locations.add(
                location_key
            )

            unique_candidates.append(
                candidate
            )

        candidates = unique_candidates[:5]

        options = []

        for candidate in candidates:

            name = candidate.get("name")
            region = candidate.get("admin1")
            country = candidate.get("country")

            parts = []

            if name:
                parts.append(name)

            if region:
                parts.append(region)

            if country:
                parts.append(country)

            if parts:
                options.append(
                    ", ".join(parts)
                )

        options = list(
            dict.fromkeys(options)
        )

        # ----------------------------------------------------
        # Build clarification message
        # ----------------------------------------------------

        if options:

            question = (
                "I found multiple places "
                f"matching '{resolution['location']}'. "
                "Which one do you mean?\n\n"
            )

            question += "\n".join(
                f"{index}. {option}"
                for index, option in enumerate(
                    options,
                    start=1,
                )
            )

        else:

            question = (
                "I couldn't uniquely identify "
                f"'{resolution['location']}'. "
                "Could you provide the region or country?"
            )

        return {
            "messages": [
                AIMessage(
                    content=question
                )
            ]
        }

    # ========================================================
    # NODE 5 — BOOKING CONFIRMATION
    # ========================================================

    def booking_confirmation_node(
        self,
        state: TravelState,
    ):
        """
        Validate the selected transport option and ask
        for explicit confirmation.

        This node NEVER creates a booking.
        """

        perception = state.get(
            "perception"
        )

        if not perception:

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I couldn't determine which "
                            "transport option you want to book."
                        )
                    )
                ],
                "pending_booking_confirmation": False,
            }

        selected_option_id = (
            perception.selected_option_id
        )

        if not selected_option_id:

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "Please provide the transport "
                            "option ID you want to book, "
                            "such as TRAIN-1."
                        )
                    )
                ],
                "pending_booking_confirmation": False,
            }

        # ----------------------------------------------------
        # Previous search results
        # ----------------------------------------------------

        transport_options = state.get(
            "transport_options",
            [],
        )

        selected_option = next(
            (
                option
                for option in transport_options
                if option.get("option_id")
                == selected_option_id
            ),
            None,
        )

        # ----------------------------------------------------
        # Option not found
        # ----------------------------------------------------

        if not selected_option:

            return {
                "messages": [
                    AIMessage(
                        content=(
                            f"I couldn't find transport option "
                            f"{selected_option_id} from the previous "
                            "search results. Please search for transport "
                            "options again."
                        )
                    )
                ],
                "selected_option_id": (
                    selected_option_id
                ),
                "pending_booking_confirmation": False,
            }

        # ----------------------------------------------------
        # Build confirmation message
        # ----------------------------------------------------

        confirmation_message = (
            f"I found {selected_option_id}.\n\n"
            f"Mode: {selected_option.get('mode')}\n"
            f"Provider: {selected_option.get('provider')}\n"
            f"From: {selected_option.get('origin')}\n"
            f"To: {selected_option.get('destination')}\n"
            f"Departure: {selected_option.get('departure_time')}\n"
            f"Arrival: {selected_option.get('arrival_time')}\n"
            f"Duration: {selected_option.get('duration_minutes')} minutes\n"
            f"Price: {selected_option.get('price')} "
            f"{selected_option.get('currency')}\n\n"
            "Do you want me to book this option?"
        )

        return {
            "messages": [
                AIMessage(
                    content=confirmation_message
                )
            ],

            "selected_option_id": (
                selected_option_id
            ),

            "pending_booking_confirmation": True,
        }


    # ========================================================
    # NODE 6 — BOOKING ALREADY EXISTS
    # ========================================================
    def booking_already_exists_node(
        self,
        state: TravelState,
    ):
        """
        Handle a booking request when the current session
        already has a confirmed booking for the selected option.

        No new booking is created.
        """

        booking = state.get("booking")

        if not booking:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "This booking has already been completed."
                        )
                    )
                ]
            }

        message = (
            "This booking has already been confirmed.\n\n"
            f"Booking ID: {booking.get('booking_id')}\n"
            f"Option: {booking.get('option_id')}\n"
            f"Mode: {booking.get('mode')}\n"
            f"Provider: {booking.get('provider')}\n"
            f"From: {booking.get('origin')}\n"
            f"To: {booking.get('destination')}\n"
            f"Travellers: {booking.get('travellers')}\n"
            f"Total: {booking.get('total_price')} "
            f"{booking.get('currency')}\n"
            f"Status: {booking.get('status')}"
        )

        return {
            "messages": [
                AIMessage(content=message)
            ],
            "pending_booking_confirmation": False,
            "selected_option_id": None,
        }

    def get_bookings_node(
        self,
        state: TravelState,
    ):
        """
        Retrieve all bookings belonging to the current user.

        IMPORTANT:
        - This node does NOT use the LLM to retrieve bookings.
        - It calls BookingService directly.
        - The database is the source of truth.
        """

        # --------------------------------------------------------
        # Get current user
        # --------------------------------------------------------

        user_id = state.get("user_id")

        if not user_id:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I couldn't determine your user account "
                            "for retrieving bookings."
                        )
                    )
                ]
            }

        # --------------------------------------------------------
        # Retrieve bookings from database
        # --------------------------------------------------------

        bookings = self.booking_service.get_user_bookings(
            user_id=user_id
        )

        # --------------------------------------------------------
        # No bookings found
        # --------------------------------------------------------

        if not bookings:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "You don't have any bookings yet."
                        )
                    )
                ]
            }

        # --------------------------------------------------------
        # Format bookings
        # --------------------------------------------------------

        lines = [
            "Here are your bookings:",
            "",
        ]

        for index, booking in enumerate(
            bookings,
            start=1,
        ):
            lines.extend(
                [
                    f"{index}. Booking ID: {booking.booking_id}",
                    f"   Option: {booking.option_id}",
                    f"   Mode: {booking.mode}",
                    f"   Provider: {booking.provider}",
                    f"   From: {booking.origin}",
                    f"   To: {booking.destination}",
                    f"   Travellers: {booking.travellers}",
                    (
                        f"   Total: "
                        f"{booking.total_price} "
                        f"{booking.currency}"
                    ),
                    f"   Status: {booking.status}",
                    f"   Created: {booking.created_at}",
                    "",
                ]
            )

        return {
            "messages": [
                AIMessage(
                    content="\n".join(lines)
                )
            ]
        }

    # ========================================================
    # NODE — BOOKING WAITING
    # ========================================================

    def booking_waiting_node(
        self,
        state: TravelState,
    ):
        """
        Handle messages where the user has not clearly
        confirmed or rejected the booking.

        Example:

            "How much was it?"
            "Which provider?"
            "I'm not sure."

        No booking is performed.
        """

        selected_option_id = state.get(
            "selected_option_id"
        )

        return {
            "messages": [
                AIMessage(
                    content=(
                        "Your booking is still waiting for "
                        "confirmation.\n\n"
                        f"Selected option: {selected_option_id}\n\n"
                        "Please reply with 'Yes' to confirm "
                        "the booking or 'No' to cancel it."
                    )
                )
            ],

            # IMPORTANT:
            # Keep the confirmation pending.
            "pending_booking_confirmation": True,
        }

    # ========================================================
    # NODE — BOOKING CANCEL
    # ========================================================

    def booking_cancel_node(
        self,
        state: TravelState,
    ):
        """
        Cancel a pending booking confirmation.

        IMPORTANT:

        No database transaction happens here.
        """

        selected_option_id = state.get(
            "selected_option_id"
        )

        return {
            "messages": [
                AIMessage(
                    content=(
                        "Okay. I did not book the transport option"
                        + (
                            f" {selected_option_id}."
                            if selected_option_id
                            else "."
                        )
                    )
                )
            ],

            # Clear pending confirmation.
            "pending_booking_confirmation": False,

            # Clear selected option.
            "selected_option_id": None,

            # No booking created.
            "booking": None,
        }

    # ========================================================
    # NODE — BOOKING EXECUTION
    # ========================================================

    def booking_execution_node(
        self,
        state: TravelState,
    ):
        """
        Execute a confirmed booking.

        This function is reached ONLY when:

            pending_booking_confirmation == True

        AND:

            perception.confirmation == "yes"

        The LLM itself does not decide to execute this node.
        Application state controls the transaction.
        """

        # ----------------------------------------------------
        # Safety check #1:
        # There must actually be a pending confirmation.
        # ----------------------------------------------------

        if not state.get(
            "pending_booking_confirmation",
            False,
        ):

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "There is no pending booking "
                            "waiting for confirmation."
                        )
                    )
                ],
                "booking": None,
            }

        # ----------------------------------------------------
        # Safety check #2:
        # Confirmation must explicitly be "yes".
        # ----------------------------------------------------

        perception = state.get(
            "perception"
        )

        confirmation = getattr(
            perception,
            "confirmation",
            "unknown",
        )

        if confirmation != "yes":

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I need an explicit confirmation "
                            "before creating the booking."
                        )
                    )
                ],
                "booking": None,
            }

        # ----------------------------------------------------
        # Read selected option
        # ----------------------------------------------------

        selected_option_id = state.get(
            "selected_option_id"
        )

        if not selected_option_id:

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I couldn't determine which "
                            "transport option to book."
                        )
                    )
                ],
                "booking": None,
            }

        # ----------------------------------------------------
        # Find selected option in trusted state
        # ----------------------------------------------------

        transport_options = state.get(
            "transport_options",
            [],
        )

        selected_option = next(
            (
                option
                for option in transport_options
                if option.get("option_id")
                == selected_option_id
            ),
            None,
        )

        if not selected_option:

            return {
                "messages": [
                    AIMessage(
                        content=(
                            f"I couldn't find {selected_option_id} "
                            "in the previous transport results. "
                            "Please search for transport options again."
                        )
                    )
                ],
                "booking": None,
                "pending_booking_confirmation": False,
            }

        # ----------------------------------------------------
        # Determine traveller count
        # ----------------------------------------------------

        travellers = (
            perception.travellers
            if perception
            else 1
        )

        # ----------------------------------------------------
        # Build trusted BookingRequest
        # ----------------------------------------------------

        request = BookingRequest(
            user_id=state["user_id"],
            session_id=state["session_id"],
            option_id=selected_option_id,
            travellers=travellers,
        )

        # ----------------------------------------------------
        # Execute booking transaction
        # ----------------------------------------------------

        try:

            booking = (
                self.booking_service.create_booking(
                    request=request,
                    selected_option=selected_option,
                )
            )

        except Exception:

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I couldn't complete the booking "
                            "right now. Please try again."
                        )
                    )
                ],
                "booking": None,
            }

        # ----------------------------------------------------
        # Build user-facing confirmation
        # ----------------------------------------------------

        booking_message = (
            "Your booking has been confirmed.\n\n"
            f"Booking ID: {booking.booking_id}\n"
            f"Option: {booking.option_id}\n"
            f"Mode: {booking.mode}\n"
            f"Provider: {booking.provider}\n"
            f"From: {booking.origin}\n"
            f"To: {booking.destination}\n"
            f"Departure: {booking.departure_time}\n"
            f"Arrival: {booking.arrival_time}\n"
            f"Travellers: {booking.travellers}\n"
            f"Total: {booking.total_price} "
            f"{booking.currency}\n"
            f"Status: {booking.status}"
        )

        return {
            "messages": [
                AIMessage(
                    content=booking_message
                )
            ],

            "booking": booking.model_dump(
                mode="json"
            ),

            # Booking is complete.
            "pending_booking_confirmation": False,

            # Clear selected option after successful booking.
            "selected_option_id": None,
        }

    # ========================================================
    # NODE 6 — AGENT / LLM
    # ========================================================

    def agent_node(
        self,
        state: TravelState,
    ):
        """
        Use the LLM to execute the travel plan and call tools.
        """

        plan = state["plan"]

        resolved_destination = state.get(
            "destination_resolution"
        )

        resolved_location = None

        if (
            resolved_destination
            and resolved_destination.get("status")
            == "resolved"
        ):

            location = (
                resolved_destination.get(
                    "location",
                    {},
                )
            )

            name = location.get("name")
            admin1 = location.get("admin1")
            country = location.get("country")

            parts = [
                value
                for value in [
                    name,
                    admin1,
                    country,
                ]
                if value
            ]

            resolved_location = ", ".join(
                parts
            )

        system_message = f"""
You are a professional travel AI assistant.

Your highest priority is factual grounding.

Follow the execution plan below.

RESOLVED DESTINATION:

{resolved_destination}

EXECUTION PLAN:

{plan.model_dump_json(indent=2)}

CANONICAL DESTINATION DISPLAY NAME:

{resolved_location}

GROUNDING RULES:

1. Use tools whenever real-time or location-specific
   information is required.

2. Never invent live information.

3. When a tool has returned information, treat that
   tool result as the authoritative source for that
   information.

4. When answering after a tool result, use ONLY facts
   supported by the tool result.

5. Do NOT add unsupported travel advice, predictions,
   recommendations, safety claims, road conditions,
   weather forecasts, activity suitability, or future
   conditions unless a tool explicitly provides those
   facts.

6. Do NOT assume that clear weather means that roads
   are clear or that an activity is safe.

7. Do NOT convert current weather information into a
   forecast for tomorrow or later.

8. If the requested information is not available from
   the available tools, clearly say that the information
   is not available.

9. You may explain information directly provided by a
   tool, but do not introduce new factual claims.

10. Preserve all units exactly as returned by tools.
    Do NOT convert, infer, or change measurement units.

11. When a tool returns a measurement with a unit,
    report the same value with the same unit.

12. Keep the answer concise and useful.

13. If the user asks for something that requires a
    different tool, use that tool rather than guessing.

14. Never claim that you checked information that you
    did not actually retrieve from a tool.

15. If a tool returns a TOOL_ERROR, do not expose the
    internal error message, exception details, stack traces,
    or implementation details to the user.

    Instead, clearly state that the requested information
    could not be retrieved right now and suggest trying again
    later.

TRANSPORT OPTION RULES:

16. When presenting transport options returned by tools,
    always include the exact option_id for each option.

17. Never invent, modify, or omit an option_id returned
    by a transport tool.

18. For transport comparison results, prefer this table
    structure:

    Option ID | Mode | Provider | Departure | Arrival | Duration | Price

19. The option_id is the user's stable identifier for
    selecting a specific transport option later.

20. When multiple transport options are returned,
    present each option separately and preserve the
    exact values returned by the tools.

21. Do not create an option_id if the tool did not
    provide one.

FINAL RESPONSE RULE:

If a tool result is present in the conversation,
summarize the tool result faithfully and avoid adding
unsupported information.
"""

        messages = [
            ("system", system_message),
            *state["messages"],
        ]

        response = self.router.invoke_with_tools(
            messages,
            self.tools,
        )

        return {
            "messages": [
                response
            ],
        }

    # ========================================================
    # ROUTER — TOOL DECISION
    # ========================================================

    def should_use_tools(
        self,
        state: TravelState,
    ):
        """
        Decide whether the latest AI message requested tools.
        """

        last_message = state["messages"][-1]

        if getattr(
            last_message,
            "tool_calls",
            None,
        ):
            return "tools"

        return "end"

    # ========================================================
    # NODE 7 — TOOLS
    # ========================================================

    def tools_node(
        self,
        state: TravelState,
    ):
        """
        Execute tools requested by the latest AI message.
        """

        last_message = state["messages"][-1]

        tool_context = self._build_tool_context(
            state
        )

        tool_messages = []

        # Preserve previously discovered options.
        transport_options = list(
            state.get(
                "transport_options",
                [],
            )
        )

        for tool_call in last_message.tool_calls:

            tool_args = dict(
                tool_call["args"]
            )

            # ------------------------------------------------
            # Add canonical destination
            # ------------------------------------------------

            if tool_context.resolved_destination:

                tool_args[
                    "resolved_destination"
                ] = (
                    tool_context
                    .resolved_destination
                    .model_dump()
                )

            enriched_tool_call = {
                **tool_call,
                "args": tool_args,
            }

            tool_message = (
                self.tool_executor.execute(
                    enriched_tool_call
                )
            )

            tool_messages.append(
                tool_message
            )

            # ------------------------------------------------
            # Capture transport options
            # ------------------------------------------------

            tool_name = tool_call["name"]

            if tool_name in {
                "search_flights",
                "search_trains",
                "search_buses",
            }:

                result = tool_message.content

                try:

                    parsed_result = json.loads(
                        result
                    )

                    if isinstance(
                        parsed_result,
                        list,
                    ):

                        for option in parsed_result:

                            if not isinstance(
                                option,
                                dict,
                            ):
                                continue

                            option_id = (
                                option.get(
                                    "option_id"
                                )
                            )

                            if (
                                option_id
                                and not any(
                                    existing.get(
                                        "option_id"
                                    )
                                    == option_id
                                    for existing
                                    in transport_options
                                )
                            ):

                                transport_options.append(
                                    option
                                )

                except (
                    json.JSONDecodeError,
                    TypeError,
                ):
                    # Malformed tool output should not
                    # crash the entire workflow.
                    pass

        return {
            "messages": tool_messages,
            "tool_context": tool_context,
            "transport_options": transport_options,
        }

    # ========================================================
    # PUBLIC RUN METHOD
    # ========================================================

    def run(
        self,
        user_message: str,
        user_id: str,
        session_id: str,
    ):
        """
        Execute one complete user turn.

        Important:

        Workflow state is persisted so that a later turn
        can continue the booking flow.
        """

        # ----------------------------------------------------
        # Save user message
        # ----------------------------------------------------

        self.memory.add_message(
            session_id,
            "human",
            user_message,
        )

        # ----------------------------------------------------
        # Load previous workflow state
        # ----------------------------------------------------

        workflow_state = (
            self.memory.get_workflow_state(
                session_id
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # selected_option_id MUST be restored here.
        #
        # Previously this was always None.
        #
        # That would break:
        #
        # Turn 3 → TRAIN-1 selected
        # Turn 4 → Yes
        #
        # because Turn 4 would lose TRAIN-1.
        # ----------------------------------------------------

        previous_selected_option_id = (
            workflow_state.get(
                "selected_option_id"
            )
        )

        # ----------------------------------------------------
        # Create initial graph state
        # ----------------------------------------------------

        initial_state: TravelState = {

            "user_message": user_message,

            "user_id": user_id,

            "session_id": session_id,

            "messages": [
                HumanMessage(
                    content=user_message
                )
            ],

            "perception": None,

            "plan": None,

            "destination_resolution": None,

            "clarification_needed": False,

            "pending_clarification": (
                workflow_state.get(
                    "pending_clarification"
                )
            ),

            "pending_destination": (
                workflow_state.get(
                    "pending_destination"
                )
            ),

            "tool_context": None,

            # ------------------------------------------------
            # Preserve previous transport options.
            # ------------------------------------------------

            "transport_options": (
                workflow_state.get(
                    "transport_options",
                    [],
                )
            ),

            # ------------------------------------------------
            # IMPORTANT:
            # Restore previous selected option.
            # ------------------------------------------------

            "selected_option_id": (
                previous_selected_option_id
            ),

            # ------------------------------------------------
            # Preserve pending confirmation state.
            # ------------------------------------------------

            "pending_booking_confirmation": (
                workflow_state.get(
                    "pending_booking_confirmation",
                    False,
                )
            ),

            # ------------------------------------------------
            # Restore previous booking information.
            # ------------------------------------------------

            "booking": workflow_state.get(
                "booking"
            ),
        }

        # ----------------------------------------------------
        # Execute graph
        # ----------------------------------------------------

        result = self.graph.invoke(
            initial_state
        )

        # ----------------------------------------------------
        # Persist workflow state
        # ----------------------------------------------------

        self.memory.save_workflow_state(
            session_id,
            {

                "pending_clarification": (
                    result.get(
                        "pending_clarification"
                    )
                ),

                "pending_destination": (
                    result.get(
                        "pending_destination"
                    )
                ),

                "transport_options": (
                    result.get(
                        "transport_options",
                        [],
                    )
                ),

                "selected_option_id": (
                    result.get(
                        "selected_option_id"
                    )
                ),

                "pending_booking_confirmation": (
                    result.get(
                        "pending_booking_confirmation",
                        False,
                    )
                ),

                # NEW:
                # Persist successful booking result.
                "booking": result.get(
                    "booking"
                ),
            },
        )

        # ----------------------------------------------------
        # Get final graph message
        # ----------------------------------------------------

        messages = result.get(
            "messages",
            [],
        )

        if not messages:

            final_message = AIMessage(
                content=(
                    "I couldn't generate a response right now."
                )
            )

        else:

            final_message = messages[-1]

        # ----------------------------------------------------
        # Save assistant response
        # ----------------------------------------------------

        if final_message.content:

            self.memory.add_message(
                session_id,
                "assistant",
                final_message.content,
            )

        # ----------------------------------------------------
        # Return useful information
        # ----------------------------------------------------

        return {

            "perception": result.get(
                "perception"
            ),

            "plan": result.get(
                "plan"
            ),

            "destination_resolution": result.get(
                "destination_resolution"
            ),

            "transport_options": result.get(
                "transport_options",
                [],
            ),

            "selected_option_id": result.get(
                "selected_option_id"
            ),

            "pending_booking_confirmation": (
                result.get(
                    "pending_booking_confirmation",
                    False,
                )
            ),

            # NEW:
            "booking": result.get(
                "booking"
            ),

            "messages": messages,

            "answer": final_message.content,
        }

    # ========================================================
    # TOOL CONTEXT BUILDER
    # ========================================================

    def _build_tool_context(
        self,
        state: TravelState,
    ) -> ToolContext:
        """
        Build normalized context passed to tools.
        """

        resolution = state.get(
            "destination_resolution"
        )

        resolved_destination = None

        if (
            resolution
            and resolution.get("status")
            == "resolved"
            and resolution.get("location")
        ):

            resolved_destination = (
                resolution["location"]
            )

        perception = state.get(
            "perception"
        )

        return ToolContext(

            resolved_destination=(
                resolved_destination
            ),

            start_date=(
                perception.start_date
                if perception
                else None
            ),

            end_date=(
                perception.end_date
                if perception
                else None
            ),

            travellers=(
                perception.travellers
                if perception
                else None
            ),

            budget=(
                perception.budget
                if perception
                else None
            ),

            currency=(
                perception.currency
                if perception
                else None
            ),

            preferences=(
                perception.preferences or []
                if perception
                else []
            ),
        )