from app.agents.graph import TravelAgentGraph
from app.agents.perception import PerceptionAgent
from app.schemas.perception import TripPerception


DATE_RANGE = "20th December 2026 to 29th December"


class Memory:
    def get_messages(self, *_args, **_kwargs):
        return []

    def get_context(self, *_args, **_kwargs):
        return {}


class FixedPerception:
    def __init__(self, result):
        self.result = result

    def understand(self, _message, _history):
        return self.result.model_copy(deep=True)


def _graph(perception):
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.memory = Memory()
    graph.perception_agent = perception
    return graph


def _state(message, *, context=None, pending=None, pending_destination=None):
    return {
        "user_message": message,
        "session_id": "date-destination-test",
        "tenant_id": "tenant-test",
        "user_id": "user-test",
        "pending_clarification": pending,
        "pending_destination": pending_destination,
        "pending_destination_candidates": [],
        "trip_context": context or {},
    }


def test_date_range_is_parsed_and_llm_date_destination_is_removed():
    class Router:
        def invoke_structured(self, _prompt, _schema):
            return TripPerception(
                intent="find_hotel",
                destination="29th december",
                original_destination="29th december",
                hotel_destination="29th december",
                start_date=None,
                end_date=None,
            )

    perception = PerceptionAgent(Router()).understand(DATE_RANGE)

    assert perception.start_date == "2026-12-20"
    assert perception.end_date == "2026-12-29"
    assert perception.destination is None
    assert perception.original_destination is None
    assert perception.hotel_destination is None


def test_hotel_request_uses_range_for_checkin_checkout_and_keeps_city():
    from langchain_core.messages import AIMessage, ToolMessage

    graph = _graph(FixedPerception(TripPerception(
        intent="find_hotel",
        destination="29th december",
        hotel_destination="29th december",
    )))
    result = graph.perception_node(_state(
        f"Find hotels in Goa from {DATE_RANGE}",
    ))
    perception = result["perception"]

    assert perception.destination == "Goa"
    assert perception.original_destination == "Goa"
    assert perception.hotel_destination == "Goa"
    assert perception.start_date == "2026-12-20"
    assert perception.end_date == "2026-12-29"

    class CapturingExecutor:
        calls = []

        def execute(self, call):
            self.calls.append(call)
            return ToolMessage(content="[]", tool_call_id=call["id"])

    graph.tool_executor = CapturingExecutor()
    graph.tools_node({
        "messages": [AIMessage(content="", tool_calls=[{
            "name": "search_hotels",
            "args": {"destination": "Wrong", "check_in_date": "wrong", "check_out_date": "wrong"},
            "id": "hotel-date-range",
            "type": "tool_call",
        }])],
        "user_message": f"Find hotels in Goa from {DATE_RANGE}",
        "user_id": "user-test", "tenant_id": "tenant-test",
        "session_id": "date-destination-test", "perception": perception,
        "destination_resolution": None, "transport_options": [], "hotel_options": [],
    })
    args = graph.tool_executor.calls[0]["args"]
    assert args["check_in_date"] == "2026-12-20"
    assert args["check_out_date"] == "2026-12-29"


def test_round_trip_flight_date_range_preserves_route_and_both_dates():
    graph = _graph(FixedPerception(TripPerception(
        intent="find_transport",
        transport_mode="flight",
        origin="New York",
        destination="29th december",
        transport_destination="29th december",
        start_date=None,
        end_date=None,
    )))
    result = graph.perception_node(_state(
        f"Find a round-trip flight from Kolkata to Delhi on {DATE_RANGE}"
    ))
    perception = result["perception"]

    assert perception.origin == "Kolkata"
    assert perception.destination == "Delhi"
    assert perception.transport_destination == "Delhi"
    assert perception.start_date == "2026-12-20"
    assert perception.end_date == "2026-12-29"
    assert perception.round_trip is True


def test_date_range_does_not_clear_unrelated_pending_question():
    graph = _graph(FixedPerception(TripPerception(
        intent="find_hotel",
        start_date=None,
        end_date=None,
    )))
    result = graph.perception_node(_state(
        DATE_RANGE,
        context={"intent": "find_hotel", "round_trip": True},
        pending="trip_details",
    ))

    assert result["perception"].start_date == "2026-12-20"
    assert result["perception"].end_date == "2026-12-29"
    assert "pending_clarification" not in result


def test_date_only_without_destination_asks_for_destination_not_geocoding():
    graph = _graph(FixedPerception(TripPerception(
        intent="find_hotel",
        destination="29th december",
        hotel_destination="29th december",
        start_date="2026-12-20",
        end_date="2026-12-29",
    )))
    extracted = graph.perception_node(_state(DATE_RANGE))
    perception = extracted["perception"]

    assert perception.destination is None
    assert perception.start_date == "2026-12-20"
    assert perception.end_date == "2026-12-29"

    class Resolver:
        def resolve(self, _location):
            raise AssertionError("A date-only request must not reach geocoding")

    graph.destination_resolver = Resolver()
    resolution = graph.destination_resolver_node({
        **_state(DATE_RANGE),
        **extracted,
    })
    assert resolution["destination_resolution"]["status"] == "not_required"

    planned = graph.planner_node({"perception": perception})
    assert planned["clarification_needed"] is True
    assert planned["plan"].clarification_questions == [
        "What city, region, or country would you like to travel to?"
    ]

    clarification = graph.planner_clarification_node({
        "plan": planned["plan"],
        "perception": perception,
        "user_message": DATE_RANGE,
    })
    assert clarification["pending_clarification"] == "destination"


def test_country_reply_does_not_qualify_stale_date_as_destination():
    graph = _graph(FixedPerception(TripPerception(
        intent="find_hotel",
        destination="India",
        original_destination="India",
        hotel_destination="India",
    )))

    context = {
        "intent": "find_hotel",
        "destination": "29th december",
        "original_destination": "29th december",
        "hotel_destination": "29th december",
        "start_date": "2026-12-20",
        "end_date": "2026-12-29",
    }
    result = graph.perception_node(_state(
        "India",
        context=context,
        pending="destination",
        pending_destination="29th december",
    ))

    assert result["perception"].destination is None
    assert result["perception"].hotel_destination is None
    assert result["perception"].start_date == "2026-12-20"
    assert result["perception"].end_date == "2026-12-29"
    assert result["pending_clarification"] is None
    assert result["pending_destination"] is None

    class Resolver:
        def resolve(self, _location):
            raise AssertionError("A date must never reach destination resolution")

    graph.destination_resolver = Resolver()
    resolved = graph.destination_resolver_node({
        **_state(
            "India",
            context=context,
            pending="destination",
            pending_destination="29th december",
        ),
        **result,
    })
    assert resolved["destination_resolution"]["status"] == "not_required"
    assert resolved["clarification_needed"] is False
