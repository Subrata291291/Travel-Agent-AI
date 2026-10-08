import json

from app.agents.graph import TravelAgentGraph
from app.api.routes.chat import ChatResponse
from app.schemas.trip import TravelPlan
from app.schemas.perception import TripPerception


def test_resolved_destination_dict_does_not_leak_into_pending_destination():
    canonical_goa = {
        "id": 1271157,
        "name": "Goa",
        "latitude": 15.33333,
        "longitude": 74.08333,
        "feature_code": "ADM1",
        "population": 1458545,
        "country": "India",
        "admin1": "Goa",
    }
    candidates = [canonical_goa]
    graph = TravelAgentGraph.__new__(TravelAgentGraph)

    result = graph.clarification_node(
        {
            "destination_resolution": {
                "status": "resolved",
                "location": canonical_goa,
                "candidates": candidates,
            },
            "plan": TravelPlan(
                goal="Plan a trip to Goa, India.",
                needs_clarification=True,
                clarification_questions=[
                    "What dates would you like to travel?"
                ],
            ),
        }
    )

    assert result["pending_destination"] == "Goa"
    assert result["pending_destination_candidates"] == candidates
    assert isinstance(result["pending_destination_candidates"][0], dict)

    response = ChatResponse(
        session_id="pending-destination-regression",
        user_id="user_demo",
        tenant_id="tenant_demo",
        pending_destination=result["pending_destination"],
    )
    assert response.pending_destination == "Goa"


def test_legacy_pending_destination_dict_restores_as_its_name():
    assert TravelAgentGraph._as_pending_destination(
        {"id": 1271157, "name": "Goa", "population": 1458545}
    ) == "Goa"


def test_destination_clarification_uses_name_not_destination_dict():
    canonical_goa = {
        "id": 1271157,
        "name": "Goa",
        "population": 1458545,
        "country": "India",
        "admin1": "Goa",
    }
    graph = TravelAgentGraph.__new__(TravelAgentGraph)

    result = graph.clarification_node(
        {
            "destination_resolution": {
                "status": "ambiguous",
                "location": canonical_goa,
                "candidates": [canonical_goa],
            },
            "pending_destination": "Goa",
        }
    )

    answer = result["messages"][0].content
    assert answer.startswith(
        "I found multiple places matching 'Goa'. Which one do you mean?"
    )
    assert "{'id':" not in answer


def test_two_turn_run_selects_persisted_destination_candidate():
    candidate = {
        "id": 1271157,
        "name": "Goa",
        "latitude": 15.33333,
        "longitude": 74.08333,
        "feature_code": "ADM1",
        "population": 1458545,
        "country": "India",
        "admin1": "Goa",
    }

    class Memory:
        def __init__(self):
            self.states = {}
            self.messages = {}

        def add_message(self, session_id, tenant_id, role, content):
            key = (session_id, tenant_id)
            self.messages.setdefault(key, []).append(
                {"role": role, "content": content}
            )

        def get_messages(self, session_id, tenant_id):
            return self.messages.get((session_id, tenant_id), [])

        def get_workflow_state(self, session_id, tenant_id):
            state = self.states.get((session_id, tenant_id), {})
            return json.loads(json.dumps(state))

        def save_workflow_state(self, session_id, user_id, tenant_id, state):
            self.states[(session_id, tenant_id)] = json.loads(
                json.dumps(state)
            )

        def get_context(self, session_id, tenant_id, user_id):
            return {}

    class Resolver:
        def __init__(self):
            self.calls = []

        def resolve(self, location):
            self.calls.append(location)
            assert location == "Goa"
            return {
                "status": "ambiguous",
                "location": location,
                "candidates": [candidate],
            }

    class Perception:
        def understand(self, message, history):
            destination = "Goa, Goa, India" if message == "1" else "Goa"
            return TripPerception(
                intent="plan_trip",
                destination=destination,
            )

    class Planner:
        def create_plan(self, perception, memory_context):
            return TravelPlan(
                goal="Plan a trip to Goa, India.",
                needs_clarification=True,
                clarification_questions=[
                    "What dates and budget would you prefer?"
                ],
            )

    graph = TravelAgentGraph()
    graph.memory = Memory()
    graph.destination_resolver = Resolver()
    graph.perception_agent = Perception()
    graph.planner_agent = Planner()

    first_turn = graph.run(
        user_message="I want to plan a trip to Goa.",
        user_id="user_demo",
        session_id="destination-selection-flow",
        tenant_id="tenant_demo",
        db=None,
    )
    assert first_turn["pending_clarification"] == "destination"
    assert first_turn["pending_destination"] == "Goa"
    assert first_turn["pending_destination_candidates"] == [candidate]

    second_turn = graph.run(
        user_message="1",
        user_id="user_demo",
        session_id="destination-selection-flow",
        tenant_id="tenant_demo",
        db=None,
    )

    assert second_turn["destination_resolution"]["status"] == "resolved"
    assert second_turn["destination_resolution"]["location"] == candidate
    assert second_turn["destination_resolution"]["candidates"] == [candidate]
    assert second_turn["clarification_needed"] is True
    assert second_turn["pending_clarification"] == "trip_details"
    assert second_turn["pending_destination"] is None
    assert second_turn["pending_destination_candidates"] == []
    assert second_turn["answer"] == "What dates and budget would you prefer?"
    assert graph.destination_resolver.calls == ["Goa"]
