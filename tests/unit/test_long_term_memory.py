from datetime import datetime, timedelta, timezone

import pytest

from app.database.models import Tenant, UserMemory
from app.memory.long_term import LongTermMemory, MemoryCandidate, rank_memories


def _owner(db, tenant_id="tenant-a"):
    db.add(Tenant(tenant_id=tenant_id, name="Test", slug=tenant_id, status="active"))
    db.commit()


def _candidate(text, topic="transport", **kwargs):
    return MemoryCandidate(text=text, topic=topic, source_quote=text, **kwargs)


def test_persists_across_service_instances_and_isolates_tenant(test_db):
    _owner(test_db)
    service = LongTermMemory()
    saved = service.upsert(test_db, "user-a", "tenant-a", _candidate("I prefer trains"))
    assert LongTermMemory().list(test_db, "user-a", "tenant-a")[0].memory_id == saved.memory_id
    assert LongTermMemory().list(test_db, "user-b", "tenant-a") == []
    assert LongTermMemory().list(test_db, "user-a", "tenant-b") == []


def test_update_supersedes_previous_and_delete_excludes_memory(test_db):
    _owner(test_db)
    service = LongTermMemory()
    old = service.upsert(test_db, "user-a", "tenant-a", _candidate("I prefer window seats", "seating"))
    new = service.upsert(test_db, "user-a", "tenant-a", _candidate("I prefer aisle seats now", "seating"))
    assert test_db.get(UserMemory, old.memory_id).status == "superseded"
    assert [m.memory_id for m in service.list(test_db, "user-a", "tenant-a")] == [new.memory_id]
    assert service.delete(test_db, "user-a", "tenant-a", new.memory_id)
    assert service.retrieve(test_db, "user-a", "tenant-a", "seat", limit=5) == []
    assert not service.delete(test_db, "user-b", "tenant-a", new.memory_id)


def test_ranking_relevance_dominates_trivial_recency(test_db):
    now = datetime.now(timezone.utc)
    old_relevant = UserMemory(
        memory_id="old", user_id="u", tenant_id="t", text="I prefer train travel",
        topic="transport", importance=1, confidence=1, source_quote="train",
        status="active", created_at=now - timedelta(days=300), updated_at=now - timedelta(days=300),
    )
    new_trivial = UserMemory(
        memory_id="new", user_id="u", tenant_id="t", text="I like red backpacks",
        topic="misc", importance=0.05, confidence=0.5, source_quote="red",
        status="active", created_at=now, updated_at=now,
    )
    ranked = rank_memories("I prefer train journeys", [new_trivial, old_relevant])
    assert ranked[0][0].memory_id == "old"


def test_semantic_domain_alias_retrieval(test_db):
    now = datetime.now(timezone.utc)
    memory = UserMemory(
        memory_id="diet", user_id="u", tenant_id="t",
        text="My partner is vegetarian", topic="dietary preferences",
        importance=0.8, confidence=0.9, source_quote="My partner is vegetarian",
        status="active", created_at=now, updated_at=now,
    )
    assert rank_memories("Find restaurants near our hotel", [memory])


def test_extraction_requires_cue_and_exact_quote_and_is_failure_safe(test_db):
    _owner(test_db)

    class Router:
        def __init__(self, result): self.result = result
        def invoke_structured(self, *_args): return self.result

    msg = "I prefer trains for long-distance trips."
    valid = {"memories": [{"text": "Prefers trains for long-distance travel", "topic": "transport",
                            "source_quote": "I prefer trains for long-distance trips.", "importance": .8,
                            "confidence": .9, "kind": "semantic"}]}
    assert LongTermMemory(Router(valid)).extract_and_store(test_db, "u", "tenant-a", "Thanks!") == 0
    assert LongTermMemory(Router(valid)).extract_and_store(test_db, "u", "tenant-a", msg) == 1
    bad = {"memories": [{"text": "Prefers trains", "topic": "transport", "source_quote": "invented quote"}]}
    assert LongTermMemory(Router(bad)).extract_and_store(test_db, "u", "tenant-a", msg) == 0
    unsupported = {"memories": [{"text": "Prefers luxury hotels", "topic": "accommodation",
                                  "source_quote": msg}]}
    assert LongTermMemory(Router(unsupported)).extract_and_store(test_db, "u", "tenant-a", msg) == 0
    assert LongTermMemory(Router(None)).extract_and_store(test_db, "u", "tenant-a", msg) == 0


def test_malformed_and_sensitive_candidates_are_rejected(test_db):
    _owner(test_db)
    with pytest.raises(ValueError):
        LongTermMemory().upsert(test_db, "u", "tenant-a", _candidate("My password is secret", "security"))
    class Router:
        def invoke_structured(self, *_args): return {"memories": "not a list"}
    assert LongTermMemory(Router()).extract_and_store(
        test_db, "u", "tenant-a", "I prefer trains"
    ) == 0


def test_temporary_trip_preferences_are_not_persisted(test_db):
    _owner(test_db)

    class Router:
        def invoke_structured(self, *_args):
            raise AssertionError("Temporary trip request should not call the LLM")

    assert LongTermMemory(Router()).extract_and_store(
        test_db, "u", "tenant-a", "I prefer a hotel with a pool for this trip"
    ) == 0
