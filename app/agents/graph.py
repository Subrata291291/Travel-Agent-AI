from typing import Annotated, TypedDict

import json

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
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


# ============================================================
# STATE
# ============================================================

class TravelState(TypedDict):
    """
    Shared state passed through every LangGraph node.

    Role:
    - Holds the current user turn.
    - Holds perception and planning results.
    - Holds destination-resolution information.
    - Holds tool execution context/results.
    - Holds transport options so a later turn can select one.
    - Holds booking-confirmation state across turns.
    """

    user_message: str
    user_id: str
    session_id: str

    messages: Annotated[list[BaseMessage], add_messages]

    perception: object | None
    plan: object | None

    destination_resolution: dict | None

    clarification_needed: bool
    pending_clarification: str | None
    pending_destination: str | None

    tool_context: ToolContext | None

    transport_options: list[dict]
    selected_option_id: str | None
    pending_booking_confirmation: bool


# ============================================================
# TRAVEL AGENT GRAPH
# ============================================================

class TravelAgentGraph:
    """
    Main LangGraph orchestration layer for the travel agent.

    Role:
    - Connect perception, destination resolution, planning, LLM/tool
      execution, clarification, and booking confirmation.
    - Keep the workflow modular so individual components can evolve
      independently.
    - Persist important multi-turn workflow state through ConversationMemory.
    """

    def __init__(self):
        # --------------------------------------------------------
        # Core application components
        # --------------------------------------------------------

        # LLMRouter is responsible for provider selection/fallback.
        self.router = LLMRouter()

        # Converts natural-language user input into structured travel intent.
        self.perception_agent = PerceptionAgent(self.router)

        # Converts structured perception into executable tasks.
        self.planner_agent = PlannerAgent(self.router)

        # Executes LangChain tool calls with retry/error handling.
        self.tool_executor = ToolExecutor()

        # Stores conversation history and workflow state between turns.
        self.memory = ConversationMemory()

        # Resolves human destination names into canonical locations.
        self.destination_resolver = DestinationResolver()

        # Load all registered travel tools once.
        self.tools = get_all_tools()

        # Build and compile the LangGraph workflow.
        self.graph = self._build_graph()

    # ========================================================
    # BUILD GRAPH
    # ========================================================

    def _build_graph(self):
        """
        Build and compile the LangGraph workflow.

        Role:
        - Defines the nodes.
        - Defines normal and conditional edges.
        - Controls the complete lifecycle of one user turn.
        """

        graph = StateGraph(TravelState)

        # ----------------------------------------------------
        # Register workflow nodes
        # ----------------------------------------------------

        graph.add_node("perception", self.perception_node)
        graph.add_node("planner", self.planner_node)
        graph.add_node("destination_resolver", self.destination_resolver_node)
        graph.add_node("clarification", self.clarification_node)
        graph.add_node("booking_confirmation", self.booking_confirmation_node)
        graph.add_node("agent", self.agent_node)
        graph.add_node("tools", self.tools_node)

        # ----------------------------------------------------
        # Start → Perception
        # ----------------------------------------------------

        graph.add_edge(START, "perception")

        # ----------------------------------------------------
        # Perception → Booking Confirmation OR Destination
        #
        # A request such as:
        #     "Book TRAIN-1"
        #
        # must not immediately execute a booking.
        # It first goes through explicit confirmation.
        # ----------------------------------------------------

        graph.add_conditional_edges(
            "perception",
            self.perception_route,
            {
                "booking": "booking_confirmation",
                "destination": "destination_resolver",
            },
        )

        # ----------------------------------------------------
        # Destination Resolver → Planner OR Clarification
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
        # Planner → Agent
        # ----------------------------------------------------

        graph.add_edge("planner", "agent")

        # ----------------------------------------------------
        # Clarification → END
        # ----------------------------------------------------

        graph.add_edge("clarification", END)

        # ----------------------------------------------------
        # Booking Confirmation → END
        #
        # Actual booking is intentionally NOT performed here.
        # This node only validates the selected option and asks
        # the user for explicit confirmation.
        # ----------------------------------------------------

        graph.add_edge("booking_confirmation", END)

        # ----------------------------------------------------
        # Agent → Tools OR END
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
        # Tools → Agent
        #
        # This creates the tool-calling loop:
        #
        # Agent → Tool → Agent → Tool → ... → Final answer
        # ----------------------------------------------------

        graph.add_edge("tools", "agent")

        return graph.compile()

    # ========================================================
    # NODE 1 — PERCEPTION
    # ========================================================

    def perception_node(self, state: TravelState):
        """
        Understand the current user message.

        Role:
        - Read the current message plus conversation history.
        - Extract intent, destination, dates, travellers, budget,
          transport mode, and selected transport option.
        - Produce structured TripPerception data.
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

    def planner_node(self, state: TravelState):
        """
        Convert perception into an executable travel plan.

        Role:
        - Combine the current perception with memory.
        - Include the resolved destination.
        - Ask the planner to determine which tasks/tools are required.
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

    def destination_resolver_node(self, state: TravelState):
        """
        Resolve the user's destination into a canonical location.

        Role:
        - Handle a previous destination clarification.
        - Resolve names such as "Manali".
        - Detect ambiguous destinations.
        - Store the resolution for tools and later LLM responses.
        """

        perception = state["perception"]
        destination = perception.destination

        pending_clarification = state.get("pending_clarification")
        pending_destination = state.get("pending_destination")

        # ----------------------------------------------------
        # Handle a destination clarification from the previous turn.
        #
        # Example:
        # Previous: "Which Manali?"
        # User:     "Himachal Pradesh"
        #
        # We combine the original destination with the user's
        # clarification so the resolver receives:
        # "Manali, Himachal Pradesh"
        # ----------------------------------------------------

        if (
            pending_clarification == "destination"
            and pending_destination
            and destination
        ):
            normalized_destination = destination.strip().lower()
            normalized_pending = pending_destination.strip().lower()

            if (
                normalized_destination != normalized_pending
                and not normalized_destination.startswith(
                    f"{normalized_pending},"
                )
            ):
                destination = (
                    f"{pending_destination}, "
                    f"{destination}"
                )

        # ----------------------------------------------------
        # Some requests do not require a destination.
        # ----------------------------------------------------

        if not destination:
            return {
                "destination_resolution": {
                    "status": "not_required"
                },
                "clarification_needed": False,
            }

        # ----------------------------------------------------
        # Resolve destination.
        # ----------------------------------------------------

        result = self.destination_resolver.resolve(destination)

        # ----------------------------------------------------
        # Successfully resolved.
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
        # Ambiguous or unresolved.
        # Store enough information for the next turn.
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
        Decide which workflow should run after perception.

        Role:
        - Route "Book TRAIN-1" style requests to the safe
          booking-confirmation node.
        - Route all other requests to destination resolution.
        """

        perception = state.get("perception")

        if (
            perception
            and perception.intent == "book_trip"
            and perception.selected_option_id
        ):
            return "booking"

        return "destination"

    # ========================================================
    # ROUTER — DESTINATION
    # ========================================================

    def destination_route(self, state: TravelState):
        """
        Decide whether destination clarification is required.

        Role:
        - Send unresolved/ambiguous destinations to clarification.
        - Send resolved destinations to the planner.
        """

        if state["clarification_needed"]:
            return "clarification"

        return "planner"

    # ========================================================
    # NODE 4 — CLARIFICATION
    # ========================================================

    def clarification_node(self, state: TravelState):
        """
        Ask the user to clarify an ambiguous destination.

        Role:
        - Format resolver candidates into a readable list.
        - Avoid showing duplicate locations.
        - Save pending clarification state through run().
        """

        resolution = state["destination_resolution"]

        candidates = resolution.get(
            "candidates",
            [],
        )

        # ----------------------------------------------------
        # Remove duplicate locations.
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

            seen_locations.add(location_key)
            unique_candidates.append(candidate)

        # Display at most five candidates.
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
                options.append(", ".join(parts))

        # Remove duplicate display names.
        options = list(dict.fromkeys(options))

        # ----------------------------------------------------
        # Build clarification question.
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
                AIMessage(content=question)
            ]
        }

    # ========================================================
    # NODE 5 — BOOKING CONFIRMATION
    # ========================================================

    def booking_confirmation_node(self, state: TravelState):
        """
        Validate the requested transport option and ask for confirmation.

        Role:
        - Read the option ID from perception.
        - Look for that option in persisted transport_options.
        - Show the exact option details.
        - NEVER perform the actual booking.
        - Mark pending_booking_confirmation=True.

        Example:
            User: "Book TRAIN-1"

        Result:
            "I found TRAIN-1 ... Do you want me to book this option?"
        """

        perception = state.get("perception")

        if not perception:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I couldn't determine which transport "
                            "option you want to book."
                        )
                    )
                ],
                "pending_booking_confirmation": False,
            }

        selected_option_id = perception.selected_option_id

        if not selected_option_id:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "Please provide the transport option ID "
                            "you want to book, such as TRAIN-1."
                        )
                    )
                ],
                "pending_booking_confirmation": False,
            }

        # ----------------------------------------------------
        # IMPORTANT:
        # transport_options come from the previous search turn.
        # run() loads them from ConversationMemory.
        # ----------------------------------------------------

        transport_options = state.get(
            "transport_options",
            [],
        )

        selected_option = next(
            (
                option
                for option in transport_options
                if option.get("option_id") == selected_option_id
            ),
            None,
        )

        # ----------------------------------------------------
        # The selected option was not found.
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
                "selected_option_id": selected_option_id,
                "pending_booking_confirmation": False,
            }

        # ----------------------------------------------------
        # Build explicit confirmation message.
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
                AIMessage(content=confirmation_message)
            ],
            "selected_option_id": selected_option_id,
            "pending_booking_confirmation": True,
        }

    # ========================================================
    # NODE 6 — AGENT / LLM
    # ========================================================

    def agent_node(self, state: TravelState):
        """
        Use the LLM to execute the plan and call tools when required.

        Role:
        - Build a grounded system prompt.
        - Give the LLM the current conversation and plan.
        - Use LLMRouter.invoke_with_tools() so provider fallback works.
        - Return an AIMessage that can either contain a final answer
          or request one/more tools.
        """

        plan = state["plan"]

        resolved_destination = state.get(
            "destination_resolution"
        )

        resolved_location = None

        if (
            resolved_destination
            and resolved_destination.get("status") == "resolved"
        ):
            location = resolved_destination.get(
                "location",
                {},
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

            resolved_location = ", ".join(parts)

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

        # Use provider fallback-aware tool calling.
        response = self.router.invoke_with_tools(
            messages,
            self.tools,
        )

        return {
            "messages": [response],
        }

    # ========================================================
    # ROUTER — TOOL DECISION
    # ========================================================

    def should_use_tools(self, state: TravelState):
        """
        Decide whether the latest AI message requested tool execution.

        Role:
        - If tool_calls exist, continue to tools.
        - Otherwise finish the current graph turn.
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

    def tools_node(self, state: TravelState):
        """
        Execute all tools requested by the latest AI message.

        Role:
        - Build normalized ToolContext.
        - Enrich tool arguments with resolved destination.
        - Execute tools through ToolExecutor.
        - Convert transport search results into dictionaries.
        - Preserve transport options in state for later booking.
        """

        last_message = state["messages"][-1]

        tool_context = self._build_tool_context(state)

        tool_messages = []

        # Start with options already persisted from earlier tool calls
        # in the same conversation.
        transport_options = list(
            state.get("transport_options", [])
        )

        for tool_call in last_message.tool_calls:
            tool_args = dict(tool_call["args"])

            # ------------------------------------------------
            # Add canonical destination information when available.
            # ------------------------------------------------

            if tool_context.resolved_destination:
                tool_args["resolved_destination"] = (
                    tool_context.resolved_destination.model_dump()
                )

            enriched_tool_call = {
                **tool_call,
                "args": tool_args,
            }

            tool_message = self.tool_executor.execute(
                enriched_tool_call
            )

            tool_messages.append(tool_message)

            # ------------------------------------------------
            # Capture transport options.
            #
            # ToolExecutor serializes list results as JSON.
            # Therefore json.loads() is the correct parser here.
            # ------------------------------------------------

            tool_name = tool_call["name"]

            if tool_name in {
                "search_flights",
                "search_trains",
                "search_buses",
            }:
                result = tool_message.content

                try:
                    parsed_result = json.loads(result)

                    if isinstance(parsed_result, list):
                        for option in parsed_result:
                            if isinstance(option, dict):
                                # Avoid duplicate options if the same
                                # result appears more than once.
                                option_id = option.get("option_id")

                                if option_id and not any(
                                    existing.get("option_id")
                                    == option_id
                                    for existing in transport_options
                                ):
                                    transport_options.append(option)

                except (json.JSONDecodeError, TypeError):
                    # A malformed/non-JSON tool response should not
                    # crash the entire agent loop.
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

        Role:
        1. Save the user message.
        2. Load persisted workflow state.
        3. Create the initial LangGraph state.
        4. Execute the graph.
        5. Persist important state for the next turn.
        6. Save the assistant response.
        7. Return the complete result to the caller.

        Important:
        The returned dictionary intentionally includes:
        - messages
        - transport_options
        - selected_option_id
        - pending_booking_confirmation

        These fields are needed by tests/API/UI and make the
        multi-turn booking flow observable.
        """

        # ----------------------------------------------------
        # Save user message in conversation memory.
        # ----------------------------------------------------

        self.memory.add_message(
            session_id,
            "human",
            user_message,
        )

        # ----------------------------------------------------
        # Load workflow state from the previous turn.
        # ----------------------------------------------------

        workflow_state = self.memory.get_workflow_state(
            session_id
        )

        # ----------------------------------------------------
        # Create the initial graph state.
        #
        # The current user message creates fresh perception/plan,
        # while workflow state preserves multi-turn information.
        # ----------------------------------------------------

        initial_state: TravelState = {
            "user_message": user_message,
            "user_id": user_id,
            "session_id": session_id,

            "messages": [
                HumanMessage(content=user_message)
            ],

            "perception": None,
            "plan": None,
            "destination_resolution": None,

            "clarification_needed": False,

            "pending_clarification": workflow_state.get(
                "pending_clarification"
            ),

            "pending_destination": workflow_state.get(
                "pending_destination"
            ),

            "tool_context": None,

            # IMPORTANT:
            # Previous transport results must survive into a later
            # "Book TRAIN-1" turn.
            "transport_options": workflow_state.get(
                "transport_options",
                []
            ),

            # This is intentionally reset for the current turn.
            # Perception will populate it when the user says
            # "Book TRAIN-1".
            "selected_option_id": None,

            "pending_booking_confirmation": workflow_state.get(
                "pending_booking_confirmation",
                False
            ),
        }

        # ----------------------------------------------------
        # Execute graph.
        # ----------------------------------------------------

        result = self.graph.invoke(
            initial_state
        )

        # ----------------------------------------------------
        # Persist workflow state.
        #
        # These values are required for multi-turn booking.
        # ----------------------------------------------------

        self.memory.save_workflow_state(
            session_id,
            {
                "pending_clarification": result.get(
                    "pending_clarification"
                ),

                "pending_destination": result.get(
                    "pending_destination"
                ),

                "transport_options": result.get(
                    "transport_options",
                    []
                ),

                "selected_option_id": result.get(
                    "selected_option_id"
                ),

                "pending_booking_confirmation": result.get(
                    "pending_booking_confirmation",
                    False
                ),
            },
        )

        # ----------------------------------------------------
        # Get final graph message.
        # ----------------------------------------------------

        messages = result.get(
            "messages",
            []
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
        # Save assistant response.
        # ----------------------------------------------------

        if final_message.content:
            self.memory.add_message(
                session_id,
                "assistant",
                final_message.content,
            )

        # ----------------------------------------------------
        # Return all useful information.
        #
        # IMPORTANT:
        # The previous version only returned perception, plan,
        # destination_resolution and answer. That made
        # selected_option_id, booking state, transport_options,
        # and messages invisible to test_langgraph.py.
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
                []
            ),

            "selected_option_id": result.get(
                "selected_option_id"
            ),

            "pending_booking_confirmation": result.get(
                "pending_booking_confirmation",
                False
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
        Build the normalized context object passed to tools.

        Role:
        - Convert destination resolution into canonical destination data.
        - Pass dates, travellers, budget, currency, and preferences.
        - Prevent None preferences from reaching tools.
        """

        resolution = state.get(
            "destination_resolution"
        )

        resolved_destination = None

        if (
            resolution
            and resolution.get("status") == "resolved"
            and resolution.get("location")
        ):
            resolved_destination = (
                resolution["location"]
            )

        perception = state.get(
            "perception"
        )

        return ToolContext(
            resolved_destination=resolved_destination,

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
