from app.agents.graph import TravelAgentGraph
from app.memory.short_term import ShortTermMemory
from app.schemas.perception import TripPerception


class Memory:
    def get_messages(self, *_args):
        return []


class Perception:
    def understand(self, _message, _history):
        # Deliberately model the stale extraction observed in production.
        return TripPerception(
            intent="find_transport",
            transport_mode="flight",
            origin="Howrah",
            destination="Manali",
        )


def _graph():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.memory = Memory()
    graph.perception_agent = Perception()
    return graph


def _state(message, **overrides):
    state = {
        "user_message": message,
        "session_id": "flight-session",
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "pending_clarification": None,
        "trip_context": {
            "intent": "find_transport",
            "transport_mode": "flight",
            "origin": "Howrah",
            "destination": "Manali",
            "transport_destination": "Manali",
        },
    }
    state.update(overrides)
    return state


def test_explicit_kolkata_origin_replaces_stale_howrah_after_failed_lookup():
    graph = _graph()
    result = graph.perception_node(_state(
        "go plam to book airticket from kolkata",
        pending_clarification="flight_destination",
    ))
    perception = result["perception"]
    assert perception.origin == "kolkata"
    assert perception.destination is None
    assert perception.transport_destination is None
    assert perception.intent == "find_transport"
    assert perception.transport_mode == "flight"

    route = graph.perception_route({
        "perception": perception,
        "user_message": "go plam to book airticket from kolkata",
        "pending_booking_confirmation": False,
    })
    assert route == "flight_destination_clarification"
    clarification = graph.flight_destination_clarification_node({"perception": perception})
    assert clarification["messages"][0].content == "Where would you like to fly to?"
    assert clarification["pending_clarification"] == "flight_destination"


def test_explicit_flight_route_keeps_hotels_manali_separate():
    graph = _graph()
    result = graph.perception_node(_state(
        "Book air ticket from Kolkata to Delhi and find hotels in Manali"
    ))
    perception = result["perception"]
    assert perception.origin == "Kolkata"
    assert perception.transport_destination == "Delhi"
    assert perception.hotel_destination == "Manali"
    assert perception.destination == "Manali"

    class HotelDestinationResolver:
        def resolve(self, query):
            assert query == "Manali"
            return {
                "status": "resolved",
                "location": {"name": "Manali", "latitude": 32.2, "longitude": 77.2},
                "candidates": [],
            }

    graph.destination_resolver = HotelDestinationResolver()
    resolved = graph.destination_resolver_node({"perception": perception})
    assert resolved["destination_resolution"]["location"]["name"] == "Manali"


def test_ok_go_ahead_without_pending_exact_action_does_not_run_tools_or_purchase():
    graph = _graph()
    perception = TripPerception(
        intent="find_transport", transport_mode="flight",
        origin="Howrah", destination="Manali",
    )
    state = {
        "perception": perception,
        "user_message": "ok go ahead",
        "pending_booking_confirmation": False,
        "pending_cancellation_booking_id": None,
        "pending_clarification": None,
    }
    assert graph.perception_route(state) == "acknowledgement"
    response = graph.acknowledgement_node(state)
    assert "specify the flight search or option" in response["messages"][0].content


def test_flight_origin_state_does_not_cross_sessions():
    memory = ShortTermMemory()
    memory.add_message("session-one", "tenant-a", "human", "Kolkata", "user-a")
    memory.add_message("session-two", "tenant-a", "human", "Howrah", "user-a")
    assert memory.get_messages("session-one", "tenant-a", "user-a")[0]["content"] == "Kolkata"
    assert memory.get_messages("session-two", "tenant-a", "user-a")[0]["content"] == "Howrah"
