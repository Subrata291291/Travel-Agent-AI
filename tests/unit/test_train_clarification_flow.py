import json

import pytest

from app.agents.graph import TravelAgentGraph
from app.schemas.perception import TripPerception


class _Memory:
    def __init__(self):
        self.states = {}
        self.messages = {}

    def add_message(self, session_id, tenant_id, role, content, user_id=None):
        self.messages.setdefault((session_id, tenant_id), []).append(
            {"role": role, "content": content}
        )

    def get_messages(self, session_id, tenant_id, user_id=None):
        return self.messages.get((session_id, tenant_id), [])

    def get_workflow_state(self, session_id, tenant_id, user_id=None):
        return json.loads(json.dumps(self.states.get((session_id, tenant_id), {})))

    def save_workflow_state(self, session_id, user_id, tenant_id, state):
        self.states[(session_id, tenant_id)] = json.loads(json.dumps(state))

    def get_context(self, session_id, tenant_id, user_id):
        return {}


class _Perception:
    def understand(self, _message, _history):
        # Emulate an LLM carrying a prior place into a short new request.
        return TripPerception(
            intent="find_transport",
            transport_mode="train",
            destination="Kashmir, Punjab, Pakistan",
            original_destination="Kashmir, Punjab, Pakistan",
            transport_destination="Kashmir, Punjab, Pakistan",
            origin="Lahore",
            start_date="2027-02-20",
        )


class _Resolver:
    def __init__(self):
        self.queries = []

    def resolve(self, query):
        self.queries.append(query)
        return {"status": "ambiguous", "location": query, "candidates": []}


def test_fresh_bare_train_search_does_not_resolve_stale_kashmir_or_slots():
    graph = TravelAgentGraph()
    graph.memory = _Memory()
    graph.perception_agent = _Perception()
    graph.destination_resolver = _Resolver()
    graph.memory.states[("old-session", "tenant")] = {
        "pending_clarification": "destination",
        "pending_destination": "Kashmir",
        "pending_destination_candidates": [
            {"name": "Kashmir", "admin1": "Punjab", "country": "Pakistan"}
        ],
        "trip_context": {
            "intent": "find_transport",
            "destination": "Kashmir, Punjab, Pakistan",
            "transport_destination": "Kashmir, Punjab, Pakistan",
            "origin": "Lahore",
            "start_date": "2027-02-20",
            "transport_mode": "train",
        },
    }

    result = graph.run(
        user_message="search train",
        user_id="user",
        session_id="new-session",
        tenant_id="tenant",
        db=None,
    )

    assert result["perception"].transport_mode == "train"
    assert result["perception"].destination is None
    assert result["perception"].origin is None
    assert result["perception"].start_date is None
    assert result["pending_clarification"] == "origin"
    assert result["answer"] == "Where will you be travelling from?"
    assert graph.destination_resolver.queries == []
    assert graph.memory.get_workflow_state("new-session", "tenant")["trip_context"]["destination"] is None


@pytest.mark.parametrize(
    ("origin", "destination", "start_date", "pending", "question"),
    [
        (None, "Manali", "2027-02-20", "origin", "Where will you be travelling from?"),
        ("Kolkata", None, "2027-02-20", "destination", "Where would you like to travel to?"),
        ("Kolkata", "Manali", None, "travel_date", "What date would you like to travel?"),
    ],
)
def test_train_search_asks_for_each_missing_required_slot(
    origin, destination, start_date, pending, question
):
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    perception = TripPerception(
        intent="find_transport",
        transport_mode="train",
        origin=origin,
        destination=destination,
        transport_destination=destination,
        start_date=start_date,
    )

    result = graph.planner_node({"perception": perception})

    assert result["clarification_needed"] is True
    assert result["pending_clarification"] == pending
    assert result["plan"].clarification_questions == [question]

