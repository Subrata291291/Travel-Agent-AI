from typing import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
)
from langgraph.graph import (
    StateGraph,
    START,
    END,
)
from langgraph.graph.message import add_messages

from app.agents.perception import PerceptionAgent
from app.agents.planner import PlannerAgent
from app.agents.executor import ToolExecutor

from app.llm.router import LLMRouter

from app.memory.conversation import ConversationMemory

from app.tools import get_all_tools
from app.tools.destination_resolver import (
    DestinationResolver,
)


# ============================================================
# STATE
# ============================================================


class TravelState(TypedDict):
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
    tool_context: dict | None


# ============================================================
# TRAVEL AGENT GRAPH
# ============================================================


class TravelAgentGraph:

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

        self.destination_resolver = (
            DestinationResolver()
        )

        # ----------------------------------------------------
        # Tools
        # ----------------------------------------------------

        self.tools = get_all_tools()

        self.llm = (
            self.router
            .get_primary_llm()
            .bind_tools(self.tools)
        )

        # ----------------------------------------------------
        # Build graph
        # ----------------------------------------------------

        self.graph = self._build_graph()

    # ========================================================
    # BUILD GRAPH
    # ========================================================

    def _build_graph(self):

        graph = StateGraph(TravelState)

        # ----------------------------------------------------
        # Nodes
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
            "agent",
            self.agent_node,
        )

        graph.add_node(
            "tools",
            self.tools_node,
        )

        # ----------------------------------------------------
        # START → Perception
        # ----------------------------------------------------

        graph.add_edge(
            START,
            "perception",
        )

        # ----------------------------------------------------
        # Perception → Planner
        # ----------------------------------------------------

        # Perception → Destination Resolver
        graph.add_edge(
            "perception",
            "destination_resolver",
        )

        # ----------------------------------------------------
        # Destination Resolver
        # → Agent OR Clarification
        # ----------------------------------------------------

        graph.add_conditional_edges(
            "destination_resolver",
            self.destination_route,
            {
                "planner": "planner",
                "clarification": "clarification",
            },
        )

        graph.add_edge(
            "planner",
            "agent",
        )

        # ----------------------------------------------------
        # Clarification → END
        # ----------------------------------------------------

        graph.add_edge(
            "clarification",
            END,
        )

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
        # ----------------------------------------------------

        graph.add_edge(
            "tools",
            "agent",
        )

        # ----------------------------------------------------
        # Compile
        # ----------------------------------------------------

        return graph.compile()

    # ========================================================
    # NODE 1 — PERCEPTION
    # ========================================================

    def perception_node(
        self,
        state: TravelState,
    ):

        conversation_history = (
            self.memory.get_messages(
                state["session_id"]
            )
        )

        perception = (
            self.perception_agent.understand(
                state["user_message"],
                conversation_history,
            )
        )

        return {
            "perception": perception
        }

    # ========================================================
    # NODE 2 — PLANNER
    # ========================================================

    def planner_node(
        self,
        state: TravelState,
    ):

        memory_context = (
            self.memory.get_context(
                state["session_id"],
                state["user_id"],
            )
        )

        memory_context[
            "resolved_destination"
        ] = (
            state[
                "destination_resolution"
            ]
        )

        plan = (
            self.planner_agent.create_plan(
                state["perception"],
                memory_context,
            )
        )

        return {
            "plan": plan
        }

    # ========================================================
    # NODE 3 — DESTINATION RESOLVER
    # ========================================================

    def destination_resolver_node(
        self,
        state: TravelState,
    ):

        perception = state["perception"]

        destination = perception.destination

        pending_clarification = state.get(
            "pending_clarification"
        )

        pending_destination = state.get(
            "pending_destination"
        )

        if (
            pending_clarification == "destination"
            and pending_destination
            and destination
        ):
            destination = (
                f"{pending_destination}, "
                f"{destination}"
            )

        # ----------------------------------------------------
        # Some requests may not require a destination.
        # Example:
        #
        # "What is the best way to travel?"
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

        result = (
            self.destination_resolver.resolve(
                destination
            )
        )

        # ----------------------------------------------------
        # Store resolution result
        # ----------------------------------------------------

        if result["status"] == "resolved":
            return {
                "destination_resolution": result,
                "clarification_needed": False,
                "pending_clarification": None,
                "pending_destination": None,
            }

        return {
            "destination_resolution": result,
            "clarification_needed": True,
            "pending_clarification": "destination",
            "pending_destination": destination,
        }

    # ========================================================
    # ROUTER — DESTINATION
    # ========================================================

    def destination_route(
        self,
        state: TravelState,
    ):

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

        resolution = (
            state["destination_resolution"]
        )

        candidates = (
            resolution.get(
                "candidates",
                [],
            )
        )

        # ----------------------------------------------------
        # Limit displayed candidates.
        #
        # We don't want to show 10+ locations
        # to the user.
        # ----------------------------------------------------

        candidates = candidates[:5]

        options = []

        for candidate in candidates:

            name = candidate.get(
                "name"
            )

            region = candidate.get(
                "admin1"
            )

            country = candidate.get(
                "country"
            )

            if region and country:

                options.append(
                    f"{name}, "
                    f"{region}, "
                    f"{country}"
                )

            elif country:

                options.append(
                    f"{name}, "
                    f"{country}"
                )

            else:

                options.append(
                    name
                )

        # ----------------------------------------------------
        # Build clarification question
        # ----------------------------------------------------

        if options:

            question = (
                "I found multiple places "
                f"matching "
                f"'{resolution['location']}'. "
                "Which one do you mean?\n\n"
            )

            question += "\n".join(
                f"{index}. {option}"
                for index, option
                in enumerate(
                    options,
                    start=1,
                )
            )

        else:

            question = (
                "I couldn't uniquely identify "
                f"'{resolution['location']}'. "
                "Could you provide the "
                "region or country?"
            )

        return {
            "messages": [
                AIMessage(
                    content=question
                )
            ]
        }

    # ========================================================
    # NODE 5 — AGENT / LLM
    # ========================================================

    def agent_node(
        self,
        state: TravelState,
    ):

        plan = state["plan"]

        resolved_destination = state.get("destination_resolution")

        resolved_location = None

        if (
            resolved_destination
            and resolved_destination.get("status") == "resolved"
        ):
            location = resolved_destination.get("location", {})

            name = location.get("name")
            admin1 = location.get("admin1")
            country = location.get("country")

            parts = [
                value
                for value in [name, admin1, country]
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

10. Keep the answer concise and useful.

11. If the user asks for something that requires a
    different tool, use that tool rather than guessing.

12. Never claim that you checked information that you
    did not actually retrieve from a tool.

FINAL RESPONSE RULE:

If a tool result is present in the conversation,
summarize the tool result faithfully and avoid adding
unsupported information.
"""

        messages = [
            (
                "system",
                system_message,
            ),
            *state["messages"],
        ]

        response = self.llm.invoke(
            messages
        )

        return {
            "messages": [
                response
            ]
        }

    # ========================================================
    # ROUTER — TOOL DECISION
    # ========================================================

    def should_use_tools(
        self,
        state: TravelState,
    ):

        last_message = (
            state["messages"][-1]
        )

        if getattr(
            last_message,
            "tool_calls",
            None,
        ):

            return "tools"

        return "end"

    # ========================================================
    # NODE 6 — TOOLS
    # ========================================================

    def tools_node(self, state: TravelState):
        last_message = state["messages"][-1]

        resolved_destination = self._get_resolved_destination(state)

        tool_messages = []

        for tool_call in last_message.tool_calls:
            tool_args = dict(tool_call["args"])

            if resolved_destination:
                tool_args.update(
                    {
                        "resolved_destination": resolved_destination,
                    }
                )

            enriched_tool_call = {
                **tool_call,
                "args": tool_args,
            }

            tool_messages.append(
                self.tool_executor.execute(enriched_tool_call)
            )

        return {
            "messages": tool_messages,
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

        # ----------------------------------------------------
        # Save user message in memory
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
        # Initial graph state
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
        }

        # ----------------------------------------------------
        # Execute graph
        # ----------------------------------------------------

        result = self.graph.invoke(
            initial_state
        )
        self.memory.save_workflow_state(
            session_id,
            {
                "pending_clarification": result.get(
                    "pending_clarification"
                ),
                "pending_destination": result.get(
                    "pending_destination"
                ),
            },
        )

        # ----------------------------------------------------
        # Get final message
        # ----------------------------------------------------

        final_message = (
            result["messages"][-1]
        )

        # ----------------------------------------------------
        # Save assistant response
        # ----------------------------------------------------

        self.memory.add_message(
            session_id,
            "assistant",
            final_message.content,
        )

        # ----------------------------------------------------
        # Return useful information
        # ----------------------------------------------------

        return {

            "perception": (
                result["perception"]
            ),

            "plan": (
                result["plan"]
            ),

            "destination_resolution": (
                result[
                    "destination_resolution"
                ]
            ),

            "answer": (
                final_message.content
            ),
        }

    def _get_resolved_destination(self, state: TravelState) -> dict | None:
        resolution = state.get("destination_resolution")

        if not resolution:
            return None

        if resolution.get("status") != "resolved":
            return None

        return resolution.get("location")

    def _build_tool_context(self, state: TravelState) -> dict:
        resolution = state.get("destination_resolution")

        if not resolution:
            return {}

        if resolution.get("status") != "resolved":
            return {}

        location = resolution.get("location")

        if not location:
            return {}

        return {
            "resolved_destination": location,
        }