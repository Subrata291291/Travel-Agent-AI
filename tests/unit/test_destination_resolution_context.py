from app.agents.graph import TravelAgentGraph
from app.schemas.perception import TripPerception
from app.tools.destination_resolver import DestinationResolver


def test_location_cleaning_before_geocoder_removes_trip_phrase_and_repeats():
    resolver = DestinationResolver()
    queries = []

    class Geocoder:
        def search_candidates(self, query, country_code=None):
            queries.append((query, country_code))
            return [{
                "id": 1, "name": "Goa", "admin1": "Goa", "country": "India",
                "country_code": "IN", "feature_code": "PPLA1", "latitude": 15.3,
                "longitude": 74.1, "admin1_id": 10,
            }]

        def get_by_id(self, _id):
            return {
                "id": 10, "name": "Goa", "feature_code": "ADM1",
                "country": "India", "country_code": "IN", "latitude": 15.3,
                "longitude": 74.1,
            }

    resolver.geocoding = Geocoder()
    result = resolver.resolve("Goa during my trip, Goa, Goa, Goa, India, Panaji")

    assert queries == [("Goa", None), ("Goa, Goa", None)]
    assert result["status"] == "resolved"
    assert result["location"]["name"] == "Goa"


def test_kashmir_india_qualifier_filters_other_country_matches():
    resolver = DestinationResolver()

    class Geocoder:
        def search_candidates(self, query, country_code=None):
            assert query == "Kashmir"
            return [
                {"id": 1, "name": "Kashmir", "country": "Iran", "country_code": "IR"},
                {"id": 2, "name": "Kashmir", "country": "Pakistan", "country_code": "PK"},
                {"id": 3, "name": "Kashmir", "country": "United States", "country_code": "US"},
            ]

    resolver.geocoding = Geocoder()
    result = resolver.resolve("Kashmir, India")

    assert result["status"] == "not_found"
    assert result["candidates"] == []


def test_unqualified_multiple_exact_places_remain_ambiguous():
    resolver = DestinationResolver()

    class Geocoder:
        def search_candidates(self, query, country_code=None):
            return [
                {"id": 1, "name": "Springfield", "country": "United States", "feature_code": "PPLA2"},
                {"id": 2, "name": "Springfield", "country": "Australia", "feature_code": "PPLA2"},
            ]

    resolver.geocoding = Geocoder()
    assert resolver.resolve("Springfield")["status"] == "ambiguous"


def test_pending_geographic_reply_is_used_and_success_clears_pending_state():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)

    class Memory:
        def get_messages(self, *_args):
            return []

    class Perception:
        def understand(self, _message, _history):
            return TripPerception(
                intent="plan_trip",
                destination="Goa during my trip, Goa, Goa, Goa, India, Panaji",
            )

    class Resolver:
        def __init__(self):
            self.queries = []

        def resolve(self, query):
            self.queries.append(query)
            return {
                "status": "resolved",
                "location": {"name": "Goa", "admin1": "Goa", "country": "India"},
                "candidates": [],
            }

    graph.memory = Memory()
    graph.perception_agent = Perception()
    graph.destination_resolver = Resolver()
    state = {
        "user_message": "Goa is a state located in the south-western coast region of India.",
        "session_id": "goa-context",
        "tenant_id": "tenant-test",
        "user_id": "user-test",
        "pending_clarification": "destination",
        "pending_destination": "Goa",
        "pending_destination_candidates": [],
        "trip_context": {"destination": "Goa", "original_destination": "Goa"},
    }
    extracted = graph.perception_node(state)
    result = graph.destination_resolver_node({**state, **extracted})

    assert extracted["perception"].destination == "Goa, India"
    assert extracted["perception"].original_destination == (
        "Goa is a state located in the south-western coast region of India."
    )
    assert graph.destination_resolver.queries == ["Goa, India"]
    assert result["destination_resolution"]["status"] == "resolved"
    assert result["pending_clarification"] is None
    assert result["pending_destination"] is None


def test_short_fresh_destination_replaces_stale_model_history_fragment():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)

    class Memory:
        def get_messages(self, *_args):
            return []

    class Perception:
        def understand(self, _message, _history):
            return TripPerception(
                intent="find_hotel",
                destination="Goa during my trip, Goa, Goa, Goa, India, Panaji",
            )

    graph.memory = Memory()
    graph.perception_agent = Perception()
    result = graph.perception_node({
        "user_message": "Goa",
        "session_id": "fresh-location",
        "tenant_id": "tenant-test",
        "user_id": "user-test",
        "pending_clarification": None,
        "trip_context": {},
    })

    assert result["perception"].destination == "Goa"
    assert result["perception"].original_destination == "Goa"


def test_numbered_candidate_selection_keeps_original_and_clears_old_pending():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    candidate = {
        "name": "Srinagar", "admin1": "Jammu and Kashmir", "country": "India",
        "latitude": 34.08, "longitude": 74.83,
    }
    perception = TripPerception(intent="plan_trip", destination="Srinagar")

    result = graph.destination_selection_node({
        "user_message": "1",
        "pending_clarification": "destination",
        "pending_destination": "Kashmir",
        "pending_destination_candidates": [candidate],
        "perception": perception,
    })

    assert perception.destination == "Srinagar, Jammu and Kashmir, India"
    assert perception.original_destination == "Kashmir"
    assert result["pending_clarification"] is None
    assert result["pending_destination_candidates"] == []

