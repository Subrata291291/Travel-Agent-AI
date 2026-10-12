from app.agents.graph import TravelAgentGraph
from app.schemas.perception import TripPerception
from app.tools.destination_resolver import DestinationResolver


class _Memory:
    def get_messages(self, *_args, **_kwargs):
        return []


class _Perception:
    def __init__(self, **fields):
        self.fields = fields

    def understand(self, _message, _history):
        return TripPerception(**self.fields)


def _graph_with_perception(message, **fields):
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.memory = _Memory()
    graph.perception_agent = _Perception(**fields)
    return graph.perception_node({
        "user_message": message,
        "session_id": "location-test",
        "tenant_id": "tenant-test",
        "user_id": "user-test",
        "pending_clarification": None,
        "pending_destination": None,
        "pending_destination_candidates": [],
        "trip_context": {},
    })["perception"]


def test_search_train_for_delhi_overrides_malformed_model_and_old_session_place():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.memory = _Memory()
    graph.perception_agent = _Perception(
        intent="find_transport",
        transport_mode="train",
        destination="India, Delhi, India Delhi",
        original_destination="India, Delhi, India Delhi",
        transport_destination="India, Delhi, India Delhi",
        origin="Kolkata",
        start_date="2027-02-20",
        end_date="2027-02-28",
        travellers=5,
        room_quantity=2,
        budget=60000,
    )
    result = graph.perception_node({
        "user_message": "Search train for Delhi",
        "session_id": "same-session",
        "tenant_id": "tenant-test",
        "user_id": "user-test",
        "pending_clarification": "destination",
        "pending_destination": "Goa",
        "pending_destination_candidates": [{"name": "Goa", "country": "India"}],
        "trip_context": {
            "intent": "find_hotel",
            "destination": "Goa",
            "original_destination": "Goa",
            "hotel_destination": "Goa",
            "transport_destination": "Goa",
        },
    })

    perception = result["perception"]
    assert perception.intent == "find_transport"
    assert perception.transport_mode == "train"
    assert perception.destination == "Delhi"
    assert perception.original_destination == "Delhi"
    assert perception.hotel_destination is None
    assert perception.transport_destination == "Delhi"
    assert perception.origin is None
    assert perception.start_date is None
    assert perception.end_date is None
    assert perception.travellers == 1
    assert perception.room_quantity is None
    assert perception.budget is None
    assert result["pending_clarification"] is None
    assert result["pending_destination_candidates"] == []


def test_train_destination_description_is_extracted_as_one_place_and_qualifier():
    perception = _graph_with_perception(
        "Find a train to Delhi, the capital of India",
        intent="find_transport",
        transport_mode="train",
        destination="India, Delhi",
        transport_destination="India, Delhi",
    )
    assert perception.destination == "Delhi, the capital of India"
    assert perception.transport_destination == "Delhi, the capital of India"


def test_destination_resolver_normalizes_capital_description_and_uses_population_evidence():
    resolver = DestinationResolver()
    queries = []
    candidates = [
        {
            "id": 1, "name": "Delhi", "admin1": "Delhi", "country": "India",
            "country_code": "IN", "feature_code": "PPLA", "population": 16_000_000,
        },
        {
            "id": 2, "name": "Delhi", "admin1": "Texas", "country": "United States",
            "country_code": "US", "feature_code": "PPLA", "population": 5_000,
        },
    ]

    class Geocoder:
        def search_candidates(self, query, country_code=None):
            queries.append(query)
            return candidates if query == "Delhi" else []

    resolver.geocoding = Geocoder()
    result = resolver.resolve("Delhi, the capital of India")

    assert queries == ["Delhi", "Delhi, Delhi"]
    assert result["status"] == "resolved"
    assert result["location"]["country"] == "India"


def test_pending_india_reply_qualifies_delhi_once():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.memory = _Memory()
    graph.perception_agent = _Perception(
        intent="find_transport",
        transport_mode="train",
        destination="India, Delhi",
        transport_destination="India, Delhi",
    )
    extracted = graph.perception_node({
        "user_message": "India",
        "session_id": "pending-delhi",
        "tenant_id": "tenant-test",
        "user_id": "user-test",
        "pending_clarification": "destination",
        "pending_destination": "Delhi",
        "pending_destination_candidates": [],
        "trip_context": {
            "intent": "find_transport",
            "destination": "Delhi",
            "transport_destination": "Delhi",
            "original_destination": "Delhi",
            "transport_mode": "train",
        },
    })

    assert extracted["perception"].destination == "Delhi, India"
    assert extracted["perception"].transport_destination == "Delhi, India"


def test_hotel_country_qualifier_and_date_range_survive_perception():
    perception = _graph_with_perception(
        "Find hotels in Goa, India from 20 December 2026 to 29 December 2026",
        intent="find_hotel",
        destination="India, Goa",
        hotel_destination="India, Goa",
        start_date=None,
        end_date=None,
    )
    assert perception.destination == "Goa, India"
    assert perception.original_destination == "Goa, India"
    assert perception.hotel_destination == "Goa, India"
    assert perception.start_date == "2026-12-20"
    assert perception.end_date == "2026-12-29"
    assert perception.origin is None


def test_flight_route_preserves_origin_destination_and_departure_date():
    perception = _graph_with_perception(
        "Find flights from Kolkata to Delhi on 20 December 2026",
        intent="find_transport",
        transport_mode="flight",
        destination="India, Delhi",
        transport_destination="India, Delhi",
        origin="Delhi",
        start_date="2026-12-20",
    )
    assert perception.origin == "Kolkata"
    assert perception.destination == "Delhi"
    assert perception.transport_destination == "Delhi"
    assert perception.start_date == "2026-12-20"

