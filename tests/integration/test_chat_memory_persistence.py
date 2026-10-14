from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import TravelAgentGraph
import app.api.routes.chat as chat_module
from app.auth.jwt import create_access_token
from app.database.connection import get_db
from app.database.connection import describe_database_session
from app.database.models import (
    ConversationMessage,
    Tenant,
    User,
    UserMemory,
    UserMemoryEmbedding,
)
from app.memory.long_term import LongTermMemory
from app.memory.vector_index import MemoryVectorIndex
from app.llm.router import LLMRouter
from app.schemas.perception import TripPerception
from app.schemas.trip import TravelPlan


class FakeEmbedder:
    model = "test-embedding"
    dimensions = 3

    def embed(self, _text):
        return [1.0, 0.0, 0.0]


class FakeExtractionRouter:
    def invoke_structured(self, prompt, schema):
        assert "I prefer travelling by train." in prompt
        return {
            "memories": [{
                "text": "Prefers travelling by train",
                "topic": "transport",
                "kind": "semantic",
                "importance": 0.8,
                "confidence": 0.95,
                "source_quote": "I prefer travelling by train.",
            }]
        }


class MultiPreferenceExtractionRouter:
    def invoke_structured(self, _prompt, _schema):
        return {"memories": [
            {"text": "Prefers travelling by train", "topic": "general", "source_quote": "I prefer travelling by train", "kind": "semantic", "importance": .8, "confidence": .9},
            {"text": "Is vegetarian", "topic": "general", "source_quote": "I am vegetarian", "kind": "semantic", "importance": .8, "confidence": .9},
            {"text": "Prefers budget hotels", "topic": "general", "source_quote": "I prefer budget hotels", "kind": "semantic", "importance": .8, "confidence": .9},
        ]}


def test_authenticated_chat_persists_preference_vector_and_messages(test_db, monkeypatch, caplog):
    caplog.set_level("INFO", logger=chat_module.__name__)
    test_db.add(Tenant(tenant_id="tenant-a", name="Test", slug="tenant-a", status="active"))
    test_db.add(User(
        user_id="user-a", tenant_id="tenant-a", email="traveler@example.test",
        name="Traveler", role="user", status="active",
    ))
    test_db.commit()

    agent = TravelAgentGraph()
    agent.memory.preferences = LongTermMemory(
        FakeExtractionRouter(), MemoryVectorIndex(FakeEmbedder())
    )

    class FakePerception:
        def understand(self, _message, _history):
            return TripPerception(intent="other")

    class FakePlanner:
        def create_plan(self, _perception, _context):
            return TravelPlan(goal="Acknowledge the preference", tasks=[])

    class FakeChatRouter:
        def invoke_with_tools(self, _messages, _tools):
            return AIMessage(content="I’ll keep your train preference in mind.")

    agent.perception_agent = FakePerception()
    agent.planner_agent = FakePlanner()
    agent.router = FakeChatRouter()
    monkeypatch.setattr(chat_module, "travel_agent_graph", agent)

    app = FastAPI()
    app.include_router(chat_module.router, prefix="/api/v1")
    def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    message = "I prefer travelling by train. Please remember this preference for future trips."
    try:
        response = TestClient(app).post(
            "/api/v1/chat",
            json={"message": message, "session_id": "memory-integration"},
            headers={"Authorization": f"Bearer {create_access_token('user-a', 'tenant-a')}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert describe_database_session(test_db).startswith("sqlite::memory:; session=")
    assert "Chat persistence database session: sqlite::memory:; session=" in caplog.text

    # Verify durable writes from a new SQLAlchemy session, not the request session.
    with Session(test_db.get_bind()) as verify_db:
        saved = verify_db.scalar(select(UserMemory).where(
            UserMemory.user_id == "user-a",
            UserMemory.tenant_id == "tenant-a",
            UserMemory.status == "active",
        ))
        assert saved is not None
        assert saved.text == "Prefers travelling by train"
        vector = verify_db.get(UserMemoryEmbedding, saved.memory_id)
        assert vector is not None
        assert vector.model == "test-embedding"
        assert len(vector.vector_json.strip("[]").split(",")) == 3

        messages = verify_db.scalars(select(ConversationMessage).where(
            ConversationMessage.tenant_id == "tenant-a",
            ConversationMessage.user_id == "user-a",
        ).order_by(ConversationMessage.message_id)).all()
        assert [item.role for item in messages] == ["human", "assistant"]
        assert messages[0].content == message
        assert "train preference" in messages[1].content


def test_extraction_failure_is_nonfatal_but_still_persists_chat(test_db, monkeypatch, caplog):
    test_db.add(Tenant(tenant_id="tenant-a", name="Test", slug="tenant-a", status="active"))
    test_db.add(User(
        user_id="user-a", tenant_id="tenant-a", email="traveler@example.test",
        name="Traveler", role="user", status="active",
    ))
    test_db.commit()
    agent = TravelAgentGraph()

    class FailingExtraction:
        def invoke_structured(self, *_args):
            raise RuntimeError("mock extraction failure")

    agent.memory.preferences = LongTermMemory(FailingExtraction(), MemoryVectorIndex(FakeEmbedder()))

    class FakePerception:
        def understand(self, _message, _history):
            return TripPerception(intent="other")

    class FakePlanner:
        def create_plan(self, _perception, _context):
            return TravelPlan(goal="Continue", tasks=[])

    class FakeChatRouter:
        def invoke_with_tools(self, _messages, _tools):
            return AIMessage(content="How can I help with your trip?")

    agent.perception_agent = FakePerception()
    agent.planner_agent = FakePlanner()
    agent.router = FakeChatRouter()
    monkeypatch.setattr(chat_module, "travel_agent_graph", agent)
    app = FastAPI()
    app.include_router(chat_module.router, prefix="/api/v1")
    def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={"message": "I prefer travelling by train.", "session_id": "failure-case"},
            headers={"Authorization": f"Bearer {create_access_token('user-a', 'tenant-a')}"},
        )
        recall = client.post(
            "/api/v1/chat",
            json={
                "message": "What travel preference have you saved for me?",
                "session_id": "failure-case",
            },
            headers={"Authorization": f"Bearer {create_access_token('user-a', 'tenant-a')}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert test_db.scalar(select(UserMemory)) is None
    assert test_db.scalar(select(ConversationMessage)) is not None
    assert "Preference extraction unavailable" in caplog.text
    assert "operation=MemoryExtraction" in caplog.text
    assert recall.status_code == 200
    assert "don't have any saved travel preferences" in recall.json()["answer"]


def test_core_provider_exhaustion_returns_503_keeps_user_message_and_workflow_state(
    test_db, monkeypatch, caplog
):
    test_db.add(Tenant(tenant_id="tenant-a", name="Test", slug="tenant-a", status="active"))
    test_db.add(User(
        user_id="user-a", tenant_id="tenant-a", email="traveler@example.test",
        name="Traveler", role="user", status="active",
    ))
    test_db.commit()

    agent = TravelAgentGraph()
    router = LLMRouter()
    router.provider_order = ["groq", "openrouter", "gemini", "openai"]

    class ProviderRateLimit(Exception):
        status_code = 429

    class FailingStructured:
        def invoke(self, _prompt):
            raise ProviderRateLimit("PRIVATE_PROVIDER_ERROR")

    class Provider:
        def with_structured_output(self, _schema, method):
            assert method == "json_mode"
            return FailingStructured()

    attempted = []
    monkeypatch.setattr(router, "get_llm", lambda name: (attempted.append(name) or Provider()))
    agent.perception_agent.understand = lambda *_args: router.invoke_structured(
        "PRIVATE_CORE_PROMPT", TripPerception
    )
    monkeypatch.setattr(chat_module, "travel_agent_graph", agent)

    session_id = "core-provider-failure"
    original_workflow = {
        "trip_context": {"destination": "Saved destination"},
        "pending_clarification": "flight_return_date",
    }
    agent.memory.save_workflow_state(
        session_id, "user-a", "tenant-a", original_workflow, db=test_db
    )

    app = FastAPI()
    app.include_router(chat_module.router, prefix="/api/v1")

    def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    message = "Find a flight for this trip. PRIVATE_USER_TEXT"
    try:
        response = TestClient(app).post(
            "/api/v1/chat",
            json={"message": message, "session_id": session_id},
            headers={"Authorization": f"Bearer {create_access_token('user-a', 'tenant-a')}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The travel assistant is temporarily unavailable. Please try again shortly."
    }
    assert response.headers.get("X-Request-ID")
    assert attempted == ["groq", "openrouter", "gemini", "openai"]
    assert agent.memory.get_workflow_state(
        session_id, "tenant-a", "user-a", db=test_db
    ) == original_workflow
    saved_messages = agent.memory.get_messages(
        session_id, "tenant-a", "user-a", db=test_db
    )
    assert [item["role"] for item in saved_messages] == ["human"]
    assert saved_messages[0]["content"] == message
    assert "PRIVATE_CORE_PROMPT" not in caplog.text
    assert "PRIVATE_PROVIDER_ERROR" not in caplog.text
    assert "PRIVATE_USER_TEXT" not in caplog.text
    assert "tenant-a" not in caplog.text


def test_authenticated_chat_can_recall_saved_preference_on_followup(test_db, monkeypatch):
    test_db.add(Tenant(tenant_id="tenant-a", name="Test", slug="tenant-a", status="active"))
    test_db.add(User(
        user_id="user-a", tenant_id="tenant-a", email="traveler@example.test",
        name="Traveler", role="user", status="active",
    ))
    test_db.commit()

    agent = TravelAgentGraph()
    agent.memory.preferences = LongTermMemory(
        FakeExtractionRouter(), MemoryVectorIndex(FakeEmbedder())
    )

    class FakePerception:
        def understand(self, _message, _history):
            return TripPerception(intent="other")

    class FakePlanner:
        def create_plan(self, _perception, _context):
            return TravelPlan(goal="Acknowledge", tasks=[])

    class FakeChatRouter:
        def invoke_with_tools(self, _messages, _tools):
            return AIMessage(content="Preference noted.")

    agent.perception_agent = FakePerception()
    agent.planner_agent = FakePlanner()
    agent.router = FakeChatRouter()
    monkeypatch.setattr(chat_module, "travel_agent_graph", agent)

    app = FastAPI()
    app.include_router(chat_module.router, prefix="/api/v1")

    def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    headers = {"Authorization": f"Bearer {create_access_token('user-a', 'tenant-a')}"}
    try:
        client = TestClient(app)
        first = client.post(
            "/api/v1/chat",
            json={
                "message": "I prefer travelling by train. Please remember this preference for all my future trips.",
                "session_id": "memory-recall",
            },
            headers=headers,
        )
        assert first.status_code == 200, first.text

        # The second turn uses authenticated identity and a fresh SQLAlchemy
        # session to prove the preference was durably saved before retrieval.
        with Session(test_db.get_bind()) as verify_db:
            saved = verify_db.scalar(select(UserMemory).where(
                UserMemory.user_id == "user-a",
                UserMemory.tenant_id == "tenant-a",
                UserMemory.status == "active",
            ))
            assert saved is not None
            context = agent.memory.get_context(
                "another-session", "tenant-a", "user-a",
                query="What travel preference have you saved for me?",
                db=verify_db,
            )
            assert context["user_preferences"] == [
                {"text": "Prefers travelling by train", "topic": "transport"}
            ]

        second = client.post(
            "/api/v1/chat",
            json={
                "message": "What travel preference have you saved for me?",
                "session_id": "memory-recall",
            },
            headers=headers,
        )
    finally:
        app.dependency_overrides.clear()

    assert second.status_code == 200, second.text
    assert second.json()["answer"] == (
        "Your saved travel preferences: Prefers travelling by train."
    )


def test_authenticated_chat_extracts_and_recalls_multiple_categories_in_new_session(test_db, monkeypatch):
    test_db.add(Tenant(tenant_id="tenant-a", name="Test", slug="tenant-a", status="active"))
    test_db.add(User(user_id="user-a", tenant_id="tenant-a", email="traveler@example.test", name="Traveler", role="user", status="active"))
    test_db.commit()
    agent = TravelAgentGraph()
    agent.memory.preferences = LongTermMemory(MultiPreferenceExtractionRouter(), MemoryVectorIndex(FakeEmbedder()))
    class FakePerception:
        calls = 0
        def understand(self, *_args):
            self.calls += 1
            return TripPerception(intent="other")
    class FakePlanner:
        def create_plan(self, *_args):
            return TravelPlan(goal="Acknowledge", tasks=[])
    class FakeChatRouter:
        def invoke_with_tools(self, *_args):
            return AIMessage(content="Preference noted.")
    perception = FakePerception()
    agent.perception_agent = perception
    agent.planner_agent = FakePlanner()
    agent.router = FakeChatRouter()
    monkeypatch.setattr(chat_module, "travel_agent_graph", agent)
    app = FastAPI()
    app.include_router(chat_module.router, prefix="/api/v1")
    def override_db():
        yield test_db
    app.dependency_overrides[get_db] = override_db
    headers = {"Authorization": f"Bearer {create_access_token('user-a', 'tenant-a')}"}
    try:
        client = TestClient(app)
        saved = client.post("/api/v1/chat", json={"message": "I prefer travelling by train. I am vegetarian. I prefer budget hotels.", "session_id": "save-prefs"}, headers=headers)
        assert saved.status_code == 200, saved.text
        recalled = client.post("/api/v1/chat", json={"message": "List every saved preference", "session_id": "new-recall-session"}, headers=headers)
    finally:
        app.dependency_overrides.clear()
    assert recalled.status_code == 200, recalled.text
    assert perception.calls == 1
    assert "Prefers travelling by train" in recalled.json()["answer"]
    assert "Is vegetarian" in recalled.json()["answer"]
    assert "Prefers budget hotels" in recalled.json()["answer"]
