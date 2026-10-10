from app.agents.graph import TravelAgentGraph
from app.memory.short_term import ShortTermMemory
from app.schemas.perception import TripPerception
from langchain_core.messages import AIMessage, ToolMessage
import json


class _Memory:
    def get_messages(self, *_args):
        return []


class _Perception:
    def understand(self, _message, _history):
        # Deliberately reproduce the stale-model result; explicit route parsing
        # must take precedence over this value and the saved workflow.
        return TripPerception(intent="plan_trip", destination="Goa")


def _graph():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.memory = _Memory()
    graph.perception_agent = _Perception()
    return graph


def test_explicit_manali_request_overrides_stale_goa_and_extracts_trip_details():
    graph = _graph()
    message = (
        "Book train tickets for 5 persons from Howrah to Manali and search "
        "best rated hotels in Manali. Bengali food should be available. We need 2 rooms."
    )
    result = graph.perception_node({
        "user_message": message,
        "session_id": "s1", "tenant_id": "t1", "user_id": "u1",
        "trip_context": {
            "destination": "Goa", "travellers": 1, "room_quantity": 1,
        },
        "pending_clarification": None,
    })
    perception = result["perception"]
    assert perception.origin == "Howrah"
    assert perception.destination == "Manali"
    assert perception.transport_destination == "Manali"
    assert perception.hotel_destination == "Manali"
    assert perception.travellers == 5
    assert perception.room_quantity == 2
    assert "Bengali food available" in perception.preferences
    assert perception.transport_mode == "train"


def test_short_howrah_reply_resolves_pending_origin():
    graph = _graph()
    result = graph.perception_node({
        "user_message": "Howrah", "session_id": "s1",
        "tenant_id": "t1", "user_id": "u1",
        "trip_context": {"destination": "Manali", "travellers": 5},
        "pending_clarification": "origin",
    })
    assert result["perception"].origin == "Howrah"
    assert result["perception"].destination == "Manali"
    assert result["perception"].travellers == 5


def test_canonical_candidate_is_persisted_in_perception():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    canonical = {"name": "Manali", "admin1": "Himachal Pradesh", "country": "India"}
    perception = TripPerception(
        intent="find_transport", destination="Goa",
        transport_destination="Goa", transport_mode="flight",
    )
    result = graph.destination_selection_node({
        "pending_clarification": "destination",
        "pending_destination_candidates": [canonical],
        "user_message": "1", "perception": perception,
    })
    assert result["destination_resolution"]["status"] == "resolved"
    assert perception.destination == "Manali, Himachal Pradesh, India"
    assert perception.transport_destination == "Manali, Himachal Pradesh, India"


def test_new_explicit_route_does_not_get_prefixed_with_old_pending_destination():
    class Resolver:
        def resolve(self, destination):
            self.destination = destination
            return {"status": "resolved", "location": {"name": destination}}

    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.destination_resolver = Resolver()
    result = graph.destination_resolver_node({
        "user_message": "from Howrah to Manali",
        "perception": TripPerception(
            intent="find_transport", origin="Howrah", destination="Manali"
        ),
        "pending_clarification": "destination",
        "pending_destination": "Goa",
        "pending_destination_candidates": [],
    })
    assert graph.destination_resolver.destination == "Manali"
    assert result["destination_resolution"]["location"]["name"] == "Manali"


def test_short_term_history_isolated_by_user_within_tenant_and_session():
    memory = ShortTermMemory()
    memory.add_message("same-session", "tenant", "human", "Manali", "user-a")
    memory.add_message("same-session", "tenant", "human", "Goa", "user-b")
    assert memory.get_messages("same-session", "tenant", "user-a")[0]["content"] == "Manali"
    assert memory.get_messages("same-session", "tenant", "user-b")[0]["content"] == "Goa"


def test_disabled_train_tool_does_not_discard_live_hotel_result_or_offer_id():
    hotel = {
        "hotel_id": "OFFER-REAL-17",
        "supplier_offer_id": "OFFER-REAL-17",
        "supplier_hotel_id": "AMADEUS-HOTEL-2",
        "destination": "Manali, Himachal Pradesh, India",
        "provider": "Amadeus",
    }

    class Executor:
        def __init__(self):
            self.calls = []

        def execute(self, call):
            self.calls.append(call)
            payload = (
                "TOOL_ERROR: search_trains failed. Error: Train search is disabled"
                if call["name"] == "search_trains"
                else json.dumps([hotel])
            )
            return ToolMessage(content=payload, tool_call_id=call["id"])

    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.tool_executor = Executor()
    calls = [
        {"name": "search_trains", "args": {"origin": "Howrah", "destination": "Manali", "departure_date": "2027-01-01"}, "id": "train-call", "type": "tool_call"},
        {"name": "search_hotels", "args": {"destination": "Goa", "check_in_date": "2027-01-01", "check_out_date": "2027-01-02"}, "id": "hotel-call", "type": "tool_call"},
    ]
    result = graph.tools_node({
        "messages": [AIMessage(content="", tool_calls=calls)],
        "user_message": "train and hotel search",
        "user_id": "u1", "tenant_id": "t1", "session_id": "s1",
        "perception": TripPerception(
            intent="plan_trip", destination="Manali, Himachal Pradesh, India",
            origin="Howrah", transport_destination="Manali", travellers=5,
            room_quantity=2, start_date="2027-01-01", end_date="2027-01-02",
        ),
        "destination_resolution": {"status": "resolved", "location": {
            "name": "Manali", "admin1": "Himachal Pradesh", "country": "India",
            "latitude": 32.24, "longitude": 77.19,
        }},
        "transport_options": [], "hotel_options": [],
    })
    assert result["transport_search_performed"] is True
    assert "authorized IRCTC Principal Service Provider" in result["transport_search_error"]
    assert result["hotel_search_performed"] is True
    assert result["hotel_options"][0]["supplier_offer_id"] == "OFFER-REAL-17"
    hotel_call_args = graph.tool_executor.calls[1]["args"]
    assert hotel_call_args["destination"] == "Manali, Himachal Pradesh, India"
    assert hotel_call_args["room_quantity"] == 2
    assert hotel_call_args["travellers"] == 5
