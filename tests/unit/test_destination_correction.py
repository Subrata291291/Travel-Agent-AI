from app.agents.graph import TravelAgentGraph
from app.database.repositories import WorkflowStateRepository
from app.memory.conversation import ConversationMemory
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
            "preferences": ["Prefers travelling by train"],
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


def test_corrected_flight_destination_does_not_reuse_stale_geographic_goa():
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

    assert graph.destination_resolver.queries == []
    assert resolved["destination_resolution"]["status"] == "not_required"
    assert extracted["pending_destination_candidates"] == []


def test_geographic_follow_up_after_correction_is_not_treated_as_old_airport_reply():
    class Resolver:
        def __init__(self):
            self.queries = []

        def resolve(self, query):
            self.queries.append(query)
            return {
                "status": "resolved",
                "location": {"name": "Manali", "admin1": "Himachal Pradesh", "country": "India"},
                "candidates": [],
            }

    class FollowUpPerception:
        def understand(self, message, _history):
            destination = "Manali, Himachal Pradesh, India" if message.startswith("Manali") else "Goa"
            return TripPerception(
                intent="find_transport", destination=destination,
                transport_destination=destination, origin="Howrah",
                travellers=1, transport_mode="flight",
            )

    graph = _graph()
    graph.destination_resolver = Resolver()
    graph.perception_agent = FollowUpPerception()
    first_state = _state(
        "Actually, change the destination to Manali.",
        pending="flight_destination",
        pending_destination="Goa",
        candidates=[{"iata_code": "GOA"}],
    )
    corrected = graph.perception_node(first_state)
    second_state = {
        **first_state,
        "user_message": "Manali, Himachal Pradesh, India",
        "pending_clarification": corrected["pending_clarification"],
        "pending_destination": corrected["pending_destination"],
        "pending_destination_candidates": corrected["pending_destination_candidates"],
        "trip_context": graph._build_trip_context(corrected["perception"]),
    }
    follow_up = graph.perception_node(second_state)
    resolved = graph.destination_resolver_node({**second_state, **follow_up})

    assert follow_up["perception"].destination == "Manali, Himachal Pradesh, India"
    # Flight destinations are handled by the airport resolver in transport
    # search; they must not be sent to the geographic destination resolver.
    assert graph.destination_resolver.queries == []
    assert resolved["destination_resolution"]["status"] == "not_required"
    assert resolved.get("pending_clarification") is None


def test_kashmir_clarification_is_replaced_by_srinagar_correction_without_concatenation():
    class GeographyPerception:
        def understand(self, _message, _history):
            # Simulate an LLM retaining the prior ambiguous choice.
            return TripPerception(
                intent="plan_trip", destination="Kashmir, Punjab, Pakistan",
                transport_destination="Kashmir, Punjab, Pakistan", origin="Howrah",
                travellers=1, transport_mode="unknown",
            )

    class Resolver:
        def __init__(self):
            self.queries = []

        def resolve(self, query):
            self.queries.append(query)
            return {"status": "unresolved", "candidates": []}

    graph = _graph()
    graph.perception_agent = GeographyPerception()
    graph.destination_resolver = Resolver()
    state = _state(
        "I mean Srinagar, Jammu and Kashmir, India. I am planning a trip from Kolkata next month.",
        pending="destination",
        pending_destination="Kashmir, Punjab, Pakistan",
        candidates=[{"name": "Kashmir", "admin1": "Punjab", "country": "Pakistan"}],
    )
    state["trip_context"]["transport_mode"] = "unknown"

    corrected = graph.perception_node(state)
    perception = corrected["perception"]
    assert perception.destination == "Srinagar, Jammu and Kashmir, India"
    assert perception.transport_destination == "Srinagar, Jammu and Kashmir, India"
    assert perception.origin == "Kolkata"
    assert perception.travellers == 2
    assert perception.start_date == "2026-11-20"
    assert perception.preferences == ["Prefers travelling by train"]
    assert corrected["pending_clarification"] is None
    assert corrected["pending_destination_candidates"] == []

    unresolved = graph.destination_resolver_node({
        **state,
        **corrected,
        # Simulate stale persisted state arriving despite the correction.
        "pending_clarification": "destination",
        "pending_destination": "Kashmir, Punjab, Pakistan",
    })
    assert graph.destination_resolver.queries == ["Srinagar, Jammu and Kashmir, India"]
    assert unresolved["pending_destination"] == "Srinagar, Jammu and Kashmir, India"

    repeated_message = (
        "My intended destination is Srinagar, India, in the Union Territory of Jammu and Kashmir. "
        "My origin is Kolkata, India. Do not use Kashmir, Punjab, Pakistan as my destination."
    )
    repeated_state = {
        **state,
        "user_message": repeated_message,
        "pending_clarification": "destination",
        "pending_destination": unresolved["pending_destination"],
        "trip_context": graph._build_trip_context(perception),
    }
    repeated = graph.perception_node(repeated_state)
    assert repeated["perception"].destination == "Srinagar, Jammu and Kashmir, India"
    assert repeated["perception"].origin == "Kolkata, India"
    assert repeated["perception"].preferences == ["Prefers travelling by train"]

    graph.destination_resolver_node({
        **repeated_state,
        **repeated,
        "pending_clarification": "destination",
        "pending_destination": "Kashmir, Punjab, Pakistan",
    })
    assert graph.destination_resolver.queries == [
        "Srinagar, Jammu and Kashmir, India",
        "Srinagar, Jammu and Kashmir, India",
    ]


def test_repeated_correction_normalizes_region_country_order_and_explicit_origin():
    class StalePerception:
        def understand(self, _message, _history):
            return TripPerception(
                intent="plan_trip", destination="Kashmir, Punjab, Pakistan",
                transport_destination="Kashmir, Punjab, Pakistan", origin="Howrah",
                travellers=1, transport_mode="unknown",
            )

    graph = _graph()
    graph.perception_agent = StalePerception()
    result = graph.perception_node(_state(
        "My intended destination is Srinagar, India, in the Union Territory of Jammu and Kashmir. "
        "My origin is Kolkata, India. Do not use Kashmir, Punjab, Pakistan as my destination.",
        pending="destination",
        pending_destination="Srinagar, Jammu and Kashmir, India",
        candidates=[{"name": "old candidate"}],
    ))

    assert result["perception"].destination == "Srinagar, Jammu and Kashmir, India"
    assert result["perception"].origin == "Kolkata, India"
    assert result["pending_clarification"] is None
    assert result["pending_destination_candidates"] == []
    assert result["perception"].preferences == ["Prefers travelling by train"]


def test_new_explicit_destination_replaces_previous_trip_destination():
    graph = _graph()
    result = graph.perception_node(_state(
        "I want to travel to Tokyo, Japan.",
        pending=None,
        pending_destination="Kashmir, Punjab, Pakistan",
    ))
    assert result["perception"].destination == "Tokyo, Japan"
    assert result["perception"].transport_destination == "Tokyo, Japan"


def test_new_session_does_not_inherit_another_sessions_pending_clarification(test_db):
    repository = WorkflowStateRepository(test_db)
    old_session_key = ConversationMemory._owned_session_id("old-session", "user")
    new_session_key = ConversationMemory._owned_session_id("new-session", "user")

    repository.save_workflow_state(
        session_id=old_session_key,
        user_id="user",
        tenant_id="tenant",
        state='{"pending_clarification":"flight_destination","pending_destination":"Goa"}',
    )

    assert repository.get_workflow_state(old_session_key, "tenant") is not None
    assert repository.get_workflow_state(new_session_key, "tenant") is None

