from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import app.api.routes.chat as chat_module
from app.agents.graph import TravelAgentGraph
from app.auth.jwt import create_access_token
from app.database.connection import get_db
from app.database.models import ConversationMessage, Tenant, User, UserMemory


def _post(client, user_id, tenant_id, session_id, message):
    return client.post(
        "/api/v1/chat",
        json={"message": message, "session_id": session_id},
        headers={"Authorization": f"Bearer {create_access_token(user_id, tenant_id)}"},
    )


def test_name_recall_uses_same_session_history_without_travel_graph(test_db, monkeypatch):
    for tenant_id in ("tenant-a", "tenant-b"):
        test_db.add(Tenant(tenant_id=tenant_id, name=tenant_id, slug=tenant_id, status="active"))
    for user_id, tenant_id in (("user-a", "tenant-a"), ("user-b", "tenant-a"), ("user-a-other-tenant", "tenant-b")):
        test_db.add(User(
            user_id=user_id, tenant_id=tenant_id, email=f"{user_id}@example.test",
            name=user_id, role="user", status="active",
        ))
    test_db.commit()

    agent = TravelAgentGraph()
    active_workflow = {
        "trip_context": {"destination": "Delhi", "intent": "plan_trip"},
        "pending_clarification": "travel_date",
    }
    agent.memory.save_workflow_state(
        "same-session", "user-a", "tenant-a", active_workflow, db=test_db
    )

    class HistoryRouter:
        calls = []

        def invoke(self, messages):
            human_messages = [content for role, content in messages if role == "human"]
            self.calls.append(human_messages)
            if any("my name is subrata" in text.casefold() for text in human_messages):
                if human_messages[-1].casefold().startswith(("what", "whst", "who")):
                    return AIMessage(content="Your name is Subrata.")
                return AIMessage(content="Nice to meet you, Subrata!")
            return AIMessage(content="I don't have that information in this conversation.")

    router = HistoryRouter()
    agent.router = router

    def unexpected_travel_call(*_args, **_kwargs):
        raise AssertionError("General conversation entered the travel workflow")

    agent.perception_agent.understand = unexpected_travel_call
    agent.planner_agent.create_plan = unexpected_travel_call
    agent.tool_executor.execute = unexpected_travel_call
    monkeypatch.setattr(chat_module, "travel_agent_graph", agent)

    app = FastAPI()
    app.include_router(chat_module.router, prefix="/api/v1")

    def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            first = _post(client, "user-a", "tenant-a", "same-session", "my name is subrata")
            follow_up = _post(client, "user-a", "tenant-a", "same-session", "What is my name?")
            other_session = _post(client, "user-a", "tenant-a", "new-session", "What is my name?")
            other_user = _post(client, "user-b", "tenant-a", "same-session", "What is my name?")
            other_tenant = _post(client, "user-a-other-tenant", "tenant-b", "same-session", "What is my name?")
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200, first.text
    assert first.json()["answer"] == "Nice to meet you, Subrata!"
    assert follow_up.status_code == 200, follow_up.text
    assert follow_up.json()["answer"] == "Your name is Subrata."
    assert other_session.json()["answer"] == "I don't have that information in this conversation."
    assert other_user.json()["answer"] == "I don't have that information in this conversation."
    assert other_tenant.json()["answer"] == "I don't have that information in this conversation."

    assert router.calls[1] == [
        "my name is subrata",
        "What is my name?",
    ]
    assert router.calls[2] == ["What is my name?"]
    assert router.calls[3] == ["What is my name?"]
    assert router.calls[4] == ["What is my name?"]
    assert test_db.query(ConversationMessage).filter_by(
        tenant_id="tenant-a", user_id="user-a"
    ).count() == 6
    assert test_db.query(ConversationMessage).filter_by(
        tenant_id="tenant-b", user_id="user-a-other-tenant"
    ).count() == 2
    assert test_db.query(UserMemory).filter_by(user_id="user-a", tenant_id="tenant-a").count() == 0
    assert agent.memory.get_workflow_state(
        "same-session", "tenant-a", "user-a", db=test_db
    )["trip_context"] == active_workflow["trip_context"]


def test_general_and_trip_request_are_routed_differently():
    assert TravelAgentGraph.start_route({"user_message": "whst is my name"}) == "general_conversation"
    assert TravelAgentGraph.start_route({"user_message": "What is a train?"}) == "general_conversation"
    assert TravelAgentGraph.start_route({"user_message": "Find a train to Delhi"}) == "perception"
    assert TravelAgentGraph.start_route({"user_message": "What is the weather in Delhi?"}) == "perception"
