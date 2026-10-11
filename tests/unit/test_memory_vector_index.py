from datetime import datetime, timezone
from types import SimpleNamespace
from sqlalchemy.orm import sessionmaker
import pytest
from sqlalchemy import select

from app.database.models import ConversationMessage, Tenant, UserMemory, UserMemoryEmbedding
from app.agents.graph import TravelAgentGraph
from app.memory.long_term import LongTermMemory
from app.memory.short_term import ShortTermMemory
from app.memory.vector_index import (
    GoogleMemoryEmbedder,
    MemoryVectorIndex,
    cosine_similarity,
    memory_fingerprint,
)
from app.agents.planner import PlannerAgent
from app.schemas.perception import TripPerception


class FakeEmbedder:
    model = "fake-embedding-v1"
    dimensions = 2

    def __init__(self, by_text=None, fail_for=()):
        self.by_text = by_text or {}
        self.fail_for = set(fail_for)
        self.calls = []

    def embed(self, text):
        self.calls.append(text)
        if text in self.fail_for:
            raise RuntimeError("provider unavailable")
        return self.by_text.get(text, [1.0, 0.0])


def _tenant(db):
    db.add(Tenant(tenant_id="tenant-a", name="A", slug="tenant-a", status="active"))
    db.commit()


def _memory(db, memory_id, user_id, text, topic="general", status="active", tenant_id="tenant-a"):
    now = datetime.now(timezone.utc)
    item = UserMemory(
        memory_id=memory_id, user_id=user_id, tenant_id=tenant_id, text=text,
        topic=topic, kind="semantic", importance=0.7, confidence=0.9,
        source_quote=text, status=status, created_at=now, updated_at=now,
    )
    db.add(item)
    db.commit()
    return item


def test_vector_semantic_retrieval_and_combined_ranking(test_db):
    _tenant(test_db)
    stored = _memory(test_db, "m1", "u1", "I prefer window seats", "seating")
    embedder = FakeEmbedder({"I prefer window seats": [1, 0], "calm overnight journeys": [1, 0]})
    index = MemoryVectorIndex(embedder)
    assert index.index_memory(test_db, stored)

    found = LongTermMemory(vector_index=index).retrieve(
        test_db, "u1", "tenant-a", "calm overnight journeys"
    )
    assert found[0][0].memory_id == "m1"
    assert found[0][1] >= 0.79
    assert cosine_similarity([1, 0], [0, 1]) == 0


def test_google_embedding_client_is_mockable_and_dimensions_are_checked():
    class Response:
        embeddings = [type("Vector", (), {"values": [3.0, 4.0]})()]

    class Models:
        def __init__(self):
            self.arguments = None

        def embed_content(self, **kwargs):
            self.arguments = kwargs
            return Response()

    class Client:
        def __init__(self):
            self.models = Models()

    client = Client()
    embedder = GoogleMemoryEmbedder("test-key", "test-model", 2, client=client)
    result = embedder.embed("preference")
    assert result == [0.6, 0.8]
    assert client.models.arguments["model"] == "test-model"
    assert client.models.arguments["contents"].endswith("preference")

    embedder.dimensions = 3
    with pytest.raises(ValueError, match="dimension"):
        embedder.embed("preference")


def test_vector_search_scopes_owner_and_excludes_inactive_or_stale_rows(test_db):
    _tenant(test_db)
    test_db.add(Tenant(tenant_id="tenant-b", name="B", slug="tenant-b", status="active"))
    test_db.commit()
    own = _memory(test_db, "own", "u1", "Prefers trains", "transport")
    other = _memory(test_db, "other", "u2", "Prefers trains", "transport")
    inactive = _memory(test_db, "inactive", "u1", "Prefers trains", "transport", "superseded")
    other_tenant = _memory(test_db, "tenant-b-row", "u1", "Prefers trains", "transport", tenant_id="tenant-b")
    index = MemoryVectorIndex(FakeEmbedder())
    for item in (own, other, inactive, other_tenant):
        index.index_memory(test_db, item)
    scores = index.semantic_scores(test_db, "u1", "tenant-a", "rail travel")
    assert set(scores) == {"own"}

    own.text = "Prefers overnight trains"
    test_db.commit()
    scores = index.semantic_scores(test_db, "u1", "tenant-a", "rail travel")
    assert "own" not in scores  # old fingerprint cannot validate edited relational text


def test_updated_memory_is_reindexed_and_delete_invalidates_vector(test_db):
    _tenant(test_db)
    item = _memory(test_db, "m1", "u1", "I prefer trains", "transport")
    embedder = FakeEmbedder()
    service = LongTermMemory(vector_index=MemoryVectorIndex(embedder))
    service.index_memory(test_db, item)
    old_fingerprint = test_db.get(UserMemoryEmbedding, "m1").fingerprint
    item.text = "I prefer buses"
    test_db.commit()
    assert service.index_memory(test_db, item)
    assert test_db.get(UserMemoryEmbedding, "m1").fingerprint == memory_fingerprint(item)
    assert test_db.get(UserMemoryEmbedding, "m1").fingerprint != old_fingerprint
    assert service.delete(test_db, "u1", "tenant-a", "m1")
    assert test_db.get(UserMemoryEmbedding, "m1") is None


def test_vector_failure_falls_back_to_existing_lexical_retrieval(test_db):
    _tenant(test_db)
    item = _memory(test_db, "m1", "u1", "I prefer trains", "transport")
    index = MemoryVectorIndex(FakeEmbedder(fail_for={"train transport"}))
    found = LongTermMemory(vector_index=index).retrieve(
        test_db, "u1", "tenant-a", "train transport"
    )
    assert found and found[0][0].memory_id == item.memory_id


def test_embedding_failure_keeps_relational_memory_committed(test_db, caplog):
    _tenant(test_db)

    class Extractor:
        def invoke_structured(self, *_args):
            return {
                "memories": [{
                    "text": "Prefers travelling by train", "topic": "transport",
                    "source_quote": "I prefer travelling by train.",
                }]
            }

    failing_embedder = FakeEmbedder(fail_for={"Prefers travelling by train"})
    service = LongTermMemory(Extractor(), MemoryVectorIndex(failing_embedder))
    assert service.extract_and_store(
        test_db, "u1", "tenant-a", "I prefer travelling by train."
    ) == 1
    assert test_db.scalar(select(UserMemory).where(UserMemory.user_id == "u1")) is not None
    assert test_db.scalar(select(UserMemoryEmbedding)) is None
    assert "Memory indexing deferred (RuntimeError)" in caplog.text


def test_live_planner_node_passes_semantic_memory_and_current_query(test_db):
    _tenant(test_db)
    item = _memory(test_db, "m1", "u1", "I prefer window seats", "seating")
    embedder = FakeEmbedder({"I prefer window seats": [1, 0], "quiet overnight journey": [1, 0]})
    service = LongTermMemory(vector_index=MemoryVectorIndex(embedder))
    service.index_memory(test_db, item)

    class MemoryContext:
        def get_context(self, session_id, tenant_id, user_id, query="", db=None):
            ranked = service.retrieve(db, user_id, tenant_id, query)
            return {"user_preferences": [{"text": memory.text} for memory, _ in ranked]}

    class Planner:
        def create_plan(self, perception, context):
            self.context = context
            return SimpleNamespace(needs_clarification=False)

    graph = SimpleNamespace(memory=MemoryContext(), planner_agent=Planner())
    state = {
        "session_id": "session", "tenant_id": "tenant-a", "user_id": "u1",
        "user_message": "quiet overnight journey", "perception": object(),
        "destination_resolution": None,
    }
    runtime = SimpleNamespace(context=SimpleNamespace(db=test_db))
    TravelAgentGraph.planner_node(graph, state, runtime)
    assert graph.planner_agent.context["user_preferences"] == [
        {"text": "I prefer window seats"}
    ]


def test_planner_explicitly_prioritizes_current_transport_over_memory():
    class Router:
        prompt = ""

        def invoke_structured(self, prompt, schema):
            self.prompt = prompt
            return SimpleNamespace(needs_clarification=False)

    router = Router()
    PlannerAgent(router).create_plan(
        TripPerception(intent="find_transport", transport_mode="flight"),
        {"user_preferences": [{"text": "Prefers trains"}]},
    )
    assert "current explicit request always overrides" in router.prompt
    assert '"transport_mode": "flight"' in router.prompt
    assert "Prefers trains" in router.prompt


def test_backfill_is_idempotent_and_resumes_after_failure(test_db, monkeypatch):
    _tenant(test_db)
    _memory(test_db, "a", "u1", "I prefer trains")
    _memory(test_db, "b", "u1", "I prefer hotels")
    embedder = FakeEmbedder(fail_for={"I prefer hotels"})
    service = LongTermMemory(vector_index=MemoryVectorIndex(embedder))
    monkeypatch.setattr("scripts.index_user_memories.SessionLocal", sessionmaker(
        bind=test_db.get_bind(), expire_on_commit=False
    ))
    from scripts.index_user_memories import index_existing_memories

    assert index_existing_memories(service) == (1, 1)
    embedder.fail_for.clear()
    assert index_existing_memories(service) == (1, 0)
    assert index_existing_memories(service) == (0, 0)
    assert test_db.get(UserMemoryEmbedding, "a") is not None
    assert test_db.get(UserMemoryEmbedding, "b") is not None


def test_short_term_history_survives_service_instance_and_is_user_scoped(test_db):
    _tenant(test_db)
    first = ShortTermMemory()
    first.add_message("session", "tenant-a", "human", "Plan a trip", "u1", db=test_db)
    first.add_message("session", "tenant-a", "assistant", "Where to?", "u1", db=test_db)
    restarted = ShortTermMemory()
    assert restarted.get_messages("session", "tenant-a", "u1", db=test_db) == [
        {"role": "human", "content": "Plan a trip"},
        {"role": "assistant", "content": "Where to?"},
    ]
    assert restarted.get_messages("session", "tenant-a", "u2", db=test_db) == []
    assert test_db.query(ConversationMessage).count() == 2
