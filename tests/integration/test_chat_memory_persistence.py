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
    assert "Preference extraction unavailable (RuntimeError)" in caplog.text
    assert recall.status_code == 200
    assert "don't have any saved travel preferences" in recall.json()["answer"]


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
