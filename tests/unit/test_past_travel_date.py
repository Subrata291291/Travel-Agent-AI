from datetime import date

from app.agents import graph as graph_module
from app.agents.graph import TravelAgentGraph
from app.schemas.perception import TripPerception


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 10)


def test_past_departure_date_is_clarified_before_search(monkeypatch):
    monkeypatch.setattr(graph_module, "date", FixedDate)
    perception = TripPerception(
        intent="find_transport",
        origin="Howrah",
        destination="Manali",
        transport_destination="Manali",
        transport_mode="flight",
        start_date="2026-01-02",
        end_date="2026-01-10",
        travellers=2,
    )
    state = {
        "perception": perception,
        "user_message": "I am planning to stay there 2nd January 2026 to 10th",
        "pending_booking_confirmation": False,
        "pending_cancellation_booking_id": None,
    }

    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    assert graph._has_past_travel_date(perception)
    assert graph.perception_route(state) == "past_travel_date_clarification"

    clarification = TravelAgentGraph.past_travel_date_clarification_node(state)
    assert "2026-01-02 has already passed" in clarification["messages"][0].content
    assert "future departure date" in clarification["messages"][0].content
    assert clarification["pending_clarification"] == "travel_date"


def test_future_departure_date_does_not_trigger_past_date_clarification(monkeypatch):
    monkeypatch.setattr(graph_module, "date", FixedDate)
    perception = TripPerception(
        intent="find_transport",
        origin="Howrah",
        destination="Manali",
        transport_destination="Manali",
        transport_mode="flight",
        start_date="2026-11-20",
    )
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    state = {
        "perception": perception,
        "user_message": "Plan a flight",
        "pending_booking_confirmation": False,
        "pending_cancellation_booking_id": None,
        "pending_clarification": None,
    }

    assert not graph._has_past_travel_date(perception)
    assert graph.perception_route(state) == "destination"
