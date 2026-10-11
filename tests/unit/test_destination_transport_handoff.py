from langchain_core.messages import AIMessage, ToolMessage

from app.agents.graph import TravelAgentGraph
from app.schemas.perception import TripPerception


CANONICAL = "Srinagar, Jammu and Kashmir, India"


class EmptyMemory:
    def get_messages(self, *_args, **_kwargs):
        return []


class CapturingExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, call):
        self.calls.append(call)
        return ToolMessage(
            content="TOOL_ERROR: airport lookup intentionally mocked",
            tool_call_id=call["id"],
        )


def _graph(perception_agent):
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.memory = EmptyMemory()
    graph.perception_agent = perception_agent
    return graph


def test_srinagar_correction_dates_alternatives_and_airport_input_stay_canonical():
    class Perception:
        def understand(self, message, _history):
            if message.startswith("I mean Srinagar"):
                return TripPerception(
                    intent="find_transport",
                    destination="Kashmir, Punjab, Pakistan",  # stale model result
                    transport_destination="Kashmir, Punjab, Pakistan",
                    origin="Howrah",
                    transport_mode="train",
                    preferences=["Prefers travelling by train"],
                )
            return TripPerception(
                intent="find_transport",
                destination=f"option 1: {CANONICAL}",
                transport_destination=f"option 1: {CANONICAL}",
                origin="Kolkata",
                start_date="2026-11-15",
                end_date="2026-11-20",
                transport_mode="flight",  # alternative transport request
            )

    graph = _graph(Perception())
    first = graph.perception_node({
        "user_message": (
            "I mean Srinagar, Jammu and Kashmir, India. I am travelling from "
            "Kolkata next month. Please use my saved preference for travelling by train."
        ),
        "session_id": "handoff", "tenant_id": "tenant", "user_id": "user",
        "pending_clarification": "destination",
        "pending_destination": "Kashmir, Punjab, Pakistan",
        "pending_destination_candidates": [
            {"name": "Kashmir", "admin1": "Punjab", "country": "Pakistan"}
        ],
        "trip_context": {
            "intent": "find_transport", "origin": "Howrah", "travellers": 2,
            "preferences": ["Prefers travelling by train"],
        },
    })
    perception = first["perception"]
    assert perception.destination == CANONICAL
    assert perception.transport_destination == CANONICAL
    assert perception.origin == "Kolkata"
    assert perception.transport_mode == "train"
    assert perception.preferences == ["Prefers travelling by train"]
    assert first["pending_destination_candidates"] == []

    # Persisted workflow context after correction/date collection is the
    # canonical destination. A later alternative-search turn may cause the
    # LLM to copy the UI's numbered line into its structured output.
    saved_context = graph._build_trip_context(perception)
    followup = graph.perception_node({
        "user_message": "Here are my dates; what alternatives are available?",
        "session_id": "handoff", "tenant_id": "tenant", "user_id": "user",
        "pending_clarification": "travel_date",
        "pending_destination": None,
        "pending_destination_candidates": [],
        "trip_context": saved_context,
    })["perception"]
    assert followup.destination == CANONICAL
    assert followup.transport_destination == CANONICAL
    assert followup.origin == "Kolkata"
    assert followup.start_date == "2026-11-15"
    assert followup.end_date == "2026-11-20"
    assert followup.preferences == ["Prefers travelling by train"]

    # The airport provider receives only the canonical place string, even if
    # both perception and the LLM tool call contain the display label.
    graph.tool_executor = CapturingExecutor()
    graph.tools_node({
        "messages": [AIMessage(content="", tool_calls=[{
            "name": "search_flights",
            "args": {
                "origin": "Howrah",
                "destination": f"option 1: {CANONICAL}",
                "departure_date": "2026-11-15",
            },
            "id": "airport-lookup", "type": "tool_call",
        }])],
        "user_message": "What alternatives are available?",
        "user_id": "user", "tenant_id": "tenant", "session_id": "handoff",
        "perception": followup,
        "destination_resolution": None,
        "transport_options": [], "hotel_options": [],
    })
    airport_call = graph.tool_executor.calls[0]
    assert airport_call["args"]["destination"] == CANONICAL
    assert airport_call["args"]["origin"] == "Kolkata"
    assert airport_call["args"]["departure_date"] == "2026-11-15"


def test_numeric_destination_selection_stores_location_fields_not_numbered_label():
    graph = _graph(None)
    perception = TripPerception(
        intent="find_transport", destination="Kashmir",
        transport_destination="Kashmir", origin="Kolkata",
        preferences=["Prefers travelling by train"],
    )
    result = graph.destination_selection_node({
        "user_message": "1",
        "pending_clarification": "destination",
        "pending_destination_candidates": [{
            "name": "Srinagar", "admin1": "Jammu and Kashmir", "country": "India",
        }],
        "perception": perception,
    })
    assert result["destination_resolution"]["location"]["name"] == "Srinagar"
    assert perception.destination == CANONICAL
    assert perception.transport_destination == CANONICAL
    assert perception.origin == "Kolkata"
    assert perception.preferences == ["Prefers travelling by train"]
