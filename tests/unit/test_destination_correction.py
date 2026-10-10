from app.agents.graph import TravelAgentGraph
from app.schemas.perception import TripPerception


class Memory:
    def get_messages(self, *_args):
        return []


class StalePerception:
    def understand(self, _message, _history):
        # Simulates a model that carries the old destination forward.
        return TripPerception(
            intent="find_transport",
            destination="Goa",
            origin="Howrah",
            travellers=1,
            transport_mode="flight",
        )


def _graph():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    graph.memory = Memory()
    graph.perception_agent = StalePerception()
    return graph


def _state(message, *, pending=None, pending_destination=None, candidates=None):
    return {
        "user_message": message,
        "session_id": "destination-correction",
        "tenant_id": "tenant",
        "user_id": "user",
        "pending_clarification": pending,
        "pending_destination": pending_destination,
        "pending_destination_candidates": candidates or [],
        "trip_context": {
            "intent": "find_transport",
            "destination": "Goa",
            "transport_destination": "Goa",
            "origin": "Howrah",
            "travellers": 2,
            "start_date": "2026-11-20",
            "transport_mode": "flight",
        },
    }


def test_natural_language_destination_correction_preserves_other_trip_fields():
    graph = _graph()
    result = graph.perception_node(_state("Actually, change the destination to Manali."))
    perception = result["perception"]

    assert perception.destination == "Manali"
    assert perception.transport_destination == "Manali"
    assert perception.origin == "Howrah"
    assert perception.travellers == 2
    assert perception.start_date == "2026-11-20"
    assert result["pending_clarification"] is None


def test_destination_correction_clears_pending_airport_clarification_and_candidates():
    graph = _graph()
    candidates = [{"iata_code": "GOA"}, {"iata_code": "GOI"}]
    result = graph.perception_node(_state(
        "Actually, change the destination to Manali.",
        pending="flight_destination",
        pending_destination="Goa",
        candidates=candidates,
    ))

    assert result["perception"].destination == "Manali"
    assert result["pending_clarification"] is None
    assert result["pending_destination"] is None
    assert result["pending_destination_candidates"] == []


def test_corrected_destination_is_resolved_without_reusing_stale_goa():
    class Resolver:
        def __init__(self):
            self.queries = []

        def resolve(self, query):
            self.queries.append(query)
            return {
                "status": "resolved",
                "location": {
                    "name": "Manali",
                    "admin1": "Himachal Pradesh",
                    "country": "India",
                },
                "candidates": [],
            }

    graph = _graph()
    graph.destination_resolver = Resolver()
    extracted = graph.perception_node(_state(
        "Actually, change the destination to Manali.",
        pending="flight_destination",
        pending_destination="Goa",
        candidates=[{"iata_code": "GOA"}],
    ))
    resolved = graph.destination_resolver_node({
        **_state(
            "Actually, change the destination to Manali.",
            pending="flight_destination",
            pending_destination="Goa",
            candidates=[{"iata_code": "GOA"}],
        ),
        **extracted,
    })

    assert graph.destination_resolver.queries == ["Manali"]
    assert resolved["destination_resolution"]["location"]["name"] == "Manali"
    assert resolved["pending_destination_candidates"] == []

