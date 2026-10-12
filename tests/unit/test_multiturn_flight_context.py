from langchain_core.messages import AIMessage, ToolMessage

from app.agents.graph import TravelAgentGraph
from app.schemas.perception import TripPerception
from app.schemas.trip import TravelPlan, TravelTask


class Memory:
    def get_messages(self, *_args, **_kwargs):
        return []

    def get_context(self, *_args, **_kwargs):
        return {"conversation_history": [], "user_preferences": []}


class ScriptedPerception:
    def understand(self, message, _history):
        if "Kolkata" in message and "Delhi" in message:
            # Simulate the model's incorrect New York enrichment. The
            # deterministic route parser must honor the user's exact text.
            return TripPerception(
                intent="find_transport", transport_mode="flight",
                origin="New York", destination="Delhi, New York, United States",
                transport_destination="Delhi, New York, United States",
                start_date="2026-11-20", travellers=1, round_trip=True,
            )
        return TripPerception(
            intent="plan_trip", transport_mode="unknown",
            origin="New York", destination="Delhi, New York, United States",
            transport_destination="Delhi, New York, United States",
        )


def _graph():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.memory = Memory()
    graph.perception_agent = ScriptedPerception()
    return graph


def _state(message, trip_context=None, pending=None):
    return {
        "user_message": message,
        "session_id": "multi-turn-flight",
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "pending_clarification": pending,
        "trip_context": trip_context,
    }


def test_exact_multiturn_flight_conversation_preserves_route_and_resolves_return_date():
    graph = _graph()
    first = graph.perception_node(_state(
        "Kolkata → Delhi on 20 November 2026 for 1 adult, round trip"
    ))
    trip = first["perception"]
    assert (trip.origin, trip.transport_destination, trip.start_date, trip.travellers) == (
        "Kolkata", "Delhi", "2026-11-20", 1,
    )
    assert trip.round_trip is True

    # The return-date clarification supplies context for both abbreviated and
    # full date responses. A hallucinated place in the model output is ignored.
    trip_context = graph._build_trip_context(trip)
    abbreviated = graph.perception_node(_state(
        "25th", trip_context, "flight_return_date"
    ))
    trip = abbreviated["perception"]
    assert trip.end_date == "2026-11-25"
    assert abbreviated["pending_clarification"] is None
    assert trip.origin == "Kolkata"
    assert trip.transport_destination == "Delhi"

    clarified = graph.perception_node(_state(
        "25th November 2026", graph._build_trip_context(trip)
    ))
    trip = clarified["perception"]
    assert trip.end_date == "2026-11-25"
    assert trip.origin == "Kolkata"
    assert trip.transport_destination == "Delhi"

    final = graph.perception_node(_state(
        "kolkata, 25th of november i will return",
        graph._build_trip_context(trip),
    ))["perception"]
    assert final.origin == "Kolkata"
    assert final.transport_destination == "Delhi"
    assert final.end_date == "2026-11-25"


def test_one_way_flight_does_not_require_hotel_checkout_or_return_date():
    graph = _graph()

    class Planner:
        def create_plan(self, *_args):
            return TravelPlan(
                goal="Find a one-way flight",
                needs_clarification=True,
                clarification_questions=["What is your intended end date or duration of stay?"],
                tasks=[TravelTask(
                    task_id="clarify-stay", task_type="clarify",
                    description="Ask for the end date or duration of stay.",
                )],
            )

    graph.planner_agent = Planner()
    trip = TripPerception(
        intent="find_transport", transport_mode="flight", origin="Kolkata",
        destination="Delhi", transport_destination="Delhi",
        start_date="2026-11-20", travellers=1,
    )
    result = graph.planner_node({
        "perception": trip, "user_message": "Find a one-way flight",
        "session_id": "multi-turn-flight", "tenant_id": "tenant-a",
        "user_id": "user-a", "destination_resolution": None,
        "pending_clarification": "trip_details",
    })
    assert result["clarification_needed"] is False
    assert result["plan"].clarification_questions == []
    assert result["pending_clarification"] is None


def test_explicit_round_trip_without_return_date_asks_for_return_date():
    graph = _graph()

    class Planner:
        def create_plan(self, *_args):
            return TravelPlan(goal="Search flights", tasks=[])

    graph.planner_agent = Planner()
    trip = TripPerception(
        intent="find_transport", transport_mode="flight", origin="Kolkata",
        destination="Delhi", transport_destination="Delhi",
        start_date="2026-11-20", round_trip=True,
    )
    state = {
        "perception": trip, "user_message": "Find a round-trip flight",
        "session_id": "multi-turn-flight", "tenant_id": "tenant-a",
        "user_id": "user-a", "destination_resolution": None,
    }
    result = graph.planner_node(state)
    assert result["clarification_needed"] is True
    state.update(result)
    clarification = graph.planner_clarification_node(state)
    assert clarification["pending_clarification"] == "flight_return_date"


def test_abbreviated_date_without_month_or_year_gets_a_focused_followup():
    graph = _graph()
    graph.planner_agent = type(
        "Planner", (), {"create_plan": lambda self, *_args: TravelPlan(goal="Search flights")}
    )()
    trip = TripPerception(
        intent="find_transport", transport_mode="flight", origin="Kolkata",
        destination="Delhi", transport_destination="Delhi", round_trip=True,
    )
    result = graph.perception_node(_state(
        "25th", graph._build_trip_context(trip), "flight_return_date"
    ))
    assert result["perception"].end_date is None
    assert result["pending_clarification"] == "flight_return_date"
    plan_result = graph.planner_node({
        "perception": result["perception"], "user_message": "25th",
        "pending_clarification": "flight_return_date",
        "session_id": "multi-turn-flight", "tenant_id": "tenant-a",
        "user_id": "user-a", "destination_resolution": None,
    })
    assert plan_result["clarification_needed"] is True
    assert "month and year" in plan_result["plan"].clarification_questions[0]


def test_explicit_destination_change_and_new_trip_replace_old_context():
    graph = _graph()
    old_context = {
        "intent": "find_transport", "origin": "Kolkata",
        "destination": "Delhi", "transport_destination": "Delhi",
        "start_date": "2026-11-20", "travellers": 1,
    }
    changed = graph.perception_node(_state(
        "Change destination to Mumbai", old_context
    ))["perception"]
    assert changed.destination == "Mumbai"
    assert changed.transport_destination == "Mumbai"

    fresh = graph.perception_node(_state(
        "New trip from Pune to Goa", old_context, "flight_return_date"
    ))
    assert fresh["perception"].origin == "Pune"
    assert fresh["perception"].transport_destination == "Goa"
    assert fresh["perception"].start_date is None
    assert fresh["pending_clarification"] is None


def test_round_trip_return_date_is_passed_to_flight_search_tool():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)

    class CapturingExecutor:
        calls = []

        def execute(self, call):
            self.calls.append(call)
            return ToolMessage(content="[]", tool_call_id=call["id"])

    graph.tool_executor = CapturingExecutor()
    trip = TripPerception(
        intent="find_transport", transport_mode="flight", origin="Kolkata",
        destination="Delhi", transport_destination="Delhi",
        start_date="2026-11-20", end_date="2026-11-25",
        travellers=1, round_trip=True,
    )
    graph.tools_node({
        "messages": [AIMessage(content="", tool_calls=[{
            "name": "search_flights",
            "args": {"origin": "Wrong", "destination": "Wrong", "departure_date": "bad"},
            "id": "round-trip-search", "type": "tool_call",
        }])],
        "user_message": "Find a return flight",
        "user_id": "user-a", "tenant_id": "tenant-a",
        "session_id": "multi-turn-flight", "perception": trip,
        "destination_resolution": None, "transport_options": [], "hotel_options": [],
    })
    args = graph.tool_executor.calls[0]["args"]
    assert args["origin"] == "Kolkata"
    assert args["destination"] == "Delhi"
    assert args["departure_date"] == "2026-11-20"
    assert args["return_date"] == "2026-11-25"
