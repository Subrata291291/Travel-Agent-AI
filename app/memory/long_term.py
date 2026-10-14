"""Persistent, evidence-backed travel preference memory."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from time import perf_counter
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import UserMemory, UserMemoryEmbedding
from app.memory.vector_index import MemoryVectorIndex
from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


class MemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=3, max_length=500)
    topic: str = Field(min_length=2, max_length=80)
    kind: str = Field(default="semantic", pattern="^(semantic|episodic|procedural)$")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_quote: str = Field(min_length=3, max_length=1000)


class MemoryExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memories: list[MemoryCandidate] = Field(default_factory=list, max_length=5)

    @model_validator(mode="before")
    @classmethod
    def normalize_candidate_list(cls, value):
        """Accept a bare candidate list as the schema's memories collection."""
        if isinstance(value, list):
            if len(value) > 5:
                raise ValueError("At most five memories may be extracted")
            # Validate every candidate; never filter or invent partial output.
            return {"memories": value}
        return value


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
_STOP_WORDS = {"a", "an", "the", "i", "me", "my", "we", "our", "for", "to", "in", "on", "with", "and", "or", "is", "are", "please", "plan", "trip", "travel", "want", "would", "like"}
_CONCEPTS = {
    "transport": {"flight", "flights", "fly", "flying", "air", "train", "rail", "bus", "coach", "transport", "transportation"},
    "seating": {"seat", "seats", "seating", "window", "aisle"},
    "diet": {"food", "diet", "dietary", "vegetarian", "vegan", "meal", "meals", "restaurant", "restaurants"},
    "accommodation": {"hotel", "hotels", "stay", "stays", "accommodation", "lodging", "hostel", "resort"},
    "accessibility": {"accessible", "accessibility", "wheelchair", "mobility", "step-free", "disability"},
    "budget": {"budget", "price", "prices", "cost", "costs", "spending"},
}
RANKING_WEIGHTS = {"relevance": 0.65, "importance": 0.20, "confidence": 0.10, "recency": 0.05}
_SENSITIVE_RE = re.compile(
    r"\b(password|passcode|otp|one.time.password|credit.card|debit.card|cvv|"
    r"social.security|aadhaar|aadhar|passport number|identity number|bank account)\b",
    re.I,
)
_PREFERENCE_CUES = re.compile(
    r"\b(i (?:always |usually |generally )?(?:prefer|like|love|need|avoid|require)|"
    r"my (?:usual|preferred|dietary|accessibility)|i am (?:vegetarian|vegan)|"
    r"from now on|going forward|please remember|i don.t eat)\b", re.I,
)
_TEMPORARY_CUES = re.compile(r"\b(this trip|for this trip|on this trip|for tonight|this weekend|for tomorrow|for next week|for these dates)\b", re.I)
_MEMORY_RECALL_CUES = re.compile(
    r"\b(?:what|which|show|list|tell me|do you remember)\b.{0,100}"
    r"\b(?:preference|preferences|remember|saved|stored|memory|memories)\b|"
    r"\bwhat do you remember about me\b",
    re.I,
)
_RECALL_ALL_CUES = re.compile(r"\b(?:all|every|each)\b.{0,40}\b(?:saved|stored)\b.{0,30}\b(?:preference|memory|memories)\b|\b(?:all|every)\s+(?:my\s+)?(?:saved\s+)?preferences\b", re.I)
MAX_RECALL_RECORDS = 500


def is_explicit_memory_recall(query: str) -> bool:
    return bool(_MEMORY_RECALL_CUES.search(query or ""))


def _normalized_topic(candidate: MemoryCandidate) -> str:
    """Derive a conflict category from evidenced preference terms."""
    evidence = (candidate.text + " " + candidate.source_quote).casefold()
    categories = (
        ("transport", r"\b(train|rail|flight|fly|air|bus|coach)\w*\b"),
        ("diet", r"\b(vegetarian|vegan|food|diet|meal)\w*\b"),
        ("accommodation", r"\b(hotel|hostel|lodging|accommodation|resort)\w*\b"),
        ("seating", r"\b(window|aisle|seat|seating)\w*\b"),
        ("accessibility", r"\b(accessib|wheelchair|mobility|step.free)\w*\b"),
    )
    matched = [name for name, pattern in categories if re.search(pattern, evidence)]
    return matched[0] if len(matched) == 1 else candidate.topic.strip().lower()


def contains_sensitive_information(value: str) -> bool:
    return bool(_SENSITIVE_RE.search(value))


def _expanded_tokens(value: str) -> set[str]:
    tokens = {token for token in _TOKEN_RE.findall(value.lower()) if token not in _STOP_WORDS}
    for concept, aliases in _CONCEPTS.items():
        if tokens & aliases:
            tokens.add(concept)
    return tokens


def _supported_by_quote(candidate: MemoryCandidate) -> bool:
    """Reject summaries whose meaningful terms are not evidenced in their quote."""
    quote_tokens = _expanded_tokens(candidate.source_quote)
    candidate_tokens = _expanded_tokens(candidate.text)
    # Normalize simple plurals without introducing a stemming dependency.
    quote_tokens |= {token[:-1] for token in quote_tokens if len(token) > 4 and token.endswith("s")}
    candidate_tokens = {
        token for token in candidate_tokens
        if token not in {"prefer", "prefers", "preference", "like", "likes", "need", "needs", "avoid", "avoids", "require", "requires", "travel", "trip"}
    }
    if not candidate_tokens:
        return False
    return len(candidate_tokens & quote_tokens) / len(candidate_tokens) >= 0.5


def rank_memories(
    query: str,
    memories: list[UserMemory],
    limit: int = 5,
    semantic_scores: dict[str, float] | None = None,
) -> list[tuple[UserMemory, float]]:
    """Rank normalized semantic/lexical relevance with stability signals."""
    semantic_scores = semantic_scores or {}
    query_tokens = _expanded_tokens(query)
    now = datetime.now(timezone.utc)
    ranked = []
    for memory in memories:
        memory_tokens = _expanded_tokens(memory.text + " " + memory.topic)
        if not query_tokens or not memory_tokens:
            relevance = 0.0
        else:
            overlap = len(query_tokens & memory_tokens)
            relevance = overlap / len(query_tokens | memory_tokens)
            # Topic/query overlap is a useful normalized signal when wording differs.
            topic_tokens = set(_TOKEN_RE.findall(memory.topic.lower()))
            if topic_tokens & query_tokens:
                relevance = min(1.0, relevance + 0.25)
        if memory.memory_id in semantic_scores:
            relevance = 0.8 * semantic_scores[memory.memory_id] + 0.2 * relevance
        age_days = max(0.0, (now - _aware(memory.updated_at)).total_seconds() / 86400)
        recency = 1.0 / (1.0 + age_days / 180.0)
        importance = min(1.0, max(0.0, float(memory.importance)))
        confidence = min(1.0, max(0.0, float(memory.confidence)))
        score = (
            RANKING_WEIGHTS["relevance"] * relevance
            + RANKING_WEIGHTS["importance"] * importance
            + RANKING_WEIGHTS["confidence"] * confidence
            + RANKING_WEIGHTS["recency"] * recency
        )
        if relevance >= 0.08:
            ranked.append((memory, score))
    return sorted(ranked, key=lambda pair: pair[1], reverse=True)[: max(0, limit)]


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class LongTermMemory:
    def __init__(self, llm_router=None, vector_index: MemoryVectorIndex | None = None):
        self.llm_router = llm_router
        self.vector_index = vector_index or MemoryVectorIndex()

    def index_memory(self, db: Session, memory: UserMemory) -> bool:
        try:
            return self.vector_index.index_memory(db, memory)
        except Exception as error:
            db.rollback()
            logger.warning("Memory indexing deferred (%s)", type(error).__name__)
            return False

    @staticmethod
    def _owned_query(db: Session, user_id: str, tenant_id: str):
        return select(UserMemory).where(
            UserMemory.user_id == user_id,
            UserMemory.tenant_id == tenant_id,
        )

    def list(self, db: Session, user_id: str, tenant_id: str, include_inactive: bool = False):
        query = self._owned_query(db, user_id, tenant_id)
        if not include_inactive:
            query = query.where(UserMemory.status == "active")
        return list(db.scalars(query.order_by(UserMemory.updated_at.desc())).all())

    def retrieve(self, db: Session, user_id: str, tenant_id: str, query: str, limit: int = 5):
        active = db.scalars(self._owned_query(db, user_id, tenant_id).where(
            UserMemory.status == "active"
        ).order_by(UserMemory.importance.desc(), UserMemory.updated_at.desc()).limit(MAX_RECALL_RECORDS)).all()
        memories = list(active)
        # A direct question about what is saved asks for the user's saved
        # records, not a similarity match against words like "saved".
        if is_explicit_memory_recall(query):
            requested_limit = MAX_RECALL_RECORDS if _RECALL_ALL_CUES.search(query) else max(0, limit)
            return [(memory, float(memory.importance)) for memory in memories[:requested_limit]]
        semantic_scores = self.vector_index.semantic_scores(db, user_id, tenant_id, query)
        return rank_memories(query, memories, limit, semantic_scores)

    def upsert(self, db: Session, user_id: str, tenant_id: str, candidate: MemoryCandidate):
        candidate = MemoryCandidate.model_validate(candidate)
        if _SENSITIVE_RE.search(candidate.text) or _SENSITIVE_RE.search(candidate.source_quote):
            raise ValueError("Sensitive information cannot be saved as memory")
        active = db.scalars(self._owned_query(db, user_id, tenant_id).where(
            UserMemory.status == "active"
        )).all()
        topic = _normalized_topic(candidate)
        existing = next((item for item in active if item.topic.strip().lower() == topic), None)
        now = datetime.now(timezone.utc)
        if existing:
            if existing.text.strip().casefold() == candidate.text.strip().casefold():
                existing.source_quote = candidate.source_quote
                existing.confidence = candidate.confidence
                existing.importance = max(existing.importance, candidate.importance)
                existing.updated_at = now
                db.commit()
                db.refresh(existing)
                self.index_memory(db, existing)
                return existing
            existing.status = "superseded"
            existing.updated_at = now
            self.vector_index.remove_memory(db, existing.memory_id)
        memory = UserMemory(
            memory_id=uuid4().hex, user_id=user_id, tenant_id=tenant_id,
            text=candidate.text.strip(), topic=topic, kind=candidate.kind,
            importance=candidate.importance, confidence=candidate.confidence,
            source_quote=candidate.source_quote.strip(), status="active",
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        self.index_memory(db, memory)
        return memory

    def delete(self, db: Session, user_id: str, tenant_id: str, memory_id: str) -> bool:
        memory = db.scalar(self._owned_query(db, user_id, tenant_id).where(
            UserMemory.memory_id == memory_id, UserMemory.status == "active"
        ))
        if not memory:
            return False
        self.vector_index.remove_memory(db, memory.memory_id)
        memory.status = "deleted"
        memory.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True

    def clear(self, db: Session, user_id: str, tenant_id: str) -> int:
        memories = db.scalars(self._owned_query(db, user_id, tenant_id).where(
            UserMemory.status == "active"
        )).all()
        for memory in memories:
            self.vector_index.remove_memory(db, memory.memory_id)
            memory.status = "deleted"
            memory.updated_at = datetime.now(timezone.utc)
        db.commit()
        return len(memories)

    def extract_and_store(self, db: Session, user_id: str, tenant_id: str, message: str) -> int:
        started = perf_counter()
        # Skip ordinary requests, transient trip details, and small talk without paying for an LLM call.
        if (
            not self.llm_router
            or not _PREFERENCE_CUES.search(message)
            or _TEMPORARY_CUES.search(message)
            or _SENSITIVE_RE.search(message)
        ):
            logger.info("Memory write outcome request_id=%s operation=MemoryExtraction extracted=0 accepted=0 rejected=0 persisted=0 embedding=skipped save=not_saved elapsed_ms=%.2f", get_request_id() or "unavailable", (perf_counter()-started)*1000)
            return 0
        prompt = (
            "Extract at most five explicit, stable travel preferences from this single user message. "
            "Return a JSON object with a 'memories' array matching the requested schema. "
            "Do not infer personal facts or sensitive attributes. Ignore destinations, dates, budgets "
            "for one trip, current booking instructions, and small talk. source_quote must be an exact "
            "substring of the message. Return an empty memories list when nothing qualifies.\n"
            f"User message: {message!r}"
        )
        try:
            result = self.llm_router.invoke_structured(prompt, MemoryExtraction)
            parsed = result if isinstance(result, MemoryExtraction) else MemoryExtraction.model_validate(result)
        except Exception as error:
            error_name = type(error).__name__
            category = (
                "provider_exhaustion"
                if error_name == "StructuredLLMUnavailable"
                else "schema_validation"
                if error_name == "ValidationError"
                else "provider_error"
            )
            logger.warning(
                "Preference extraction unavailable request_id=%s operation=MemoryExtraction category=%s",
                get_request_id() or "unavailable",
                category,
            )
            logger.info("Memory write outcome request_id=%s operation=MemoryExtraction extracted=0 accepted=0 rejected=0 persisted=0 embedding=skipped save=not_saved elapsed_ms=%.2f", get_request_id() or "unavailable", (perf_counter()-started)*1000)
            return 0
        stored = 0
        rejected = 0
        embedding = "not_attempted"
        for candidate in parsed.memories:
            if (
                candidate.source_quote not in message
                or not _PREFERENCE_CUES.search(candidate.source_quote)
                or _TEMPORARY_CUES.search(candidate.source_quote)
                or _SENSITIVE_RE.search(candidate.text)
                or not _supported_by_quote(candidate)
            ):
                rejected += 1
                logger.info("Memory candidate rejected request_id=%s operation=MemoryExtraction reason=unsupported_or_unsafe", get_request_id() or "unavailable")
                continue
            try:
                candidate = candidate.model_copy(update={"topic": _normalized_topic(candidate)})
                memory = self.upsert(db, user_id, tenant_id, candidate)
                stored += 1
                embedding = "indexed" if db.get(UserMemoryEmbedding, memory.memory_id) else "deferred"
            except (ValueError, ValidationError):
                rejected += 1
                continue
            except Exception as error:
                db.rollback()
                error_name = type(error).__name__
                category = (
                    error_name
                    if error_name in {"IntegrityError", "OperationalError"}
                    else "persistence_error"
                )
                logger.warning(
                    "Preference persistence failed request_id=%s category=%s",
                    get_request_id() or "unavailable",
                    category,
                )
        logger.info("Memory write outcome request_id=%s operation=MemoryPersistence extracted=%d accepted=%d rejected=%d persisted=%d embedding=%s save=%s elapsed_ms=%.2f", get_request_id() or "unavailable", len(parsed.memories), stored + rejected, rejected, stored, embedding, "saved" if stored else "not_saved", (perf_counter()-started)*1000)
        return stored
