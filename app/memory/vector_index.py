"""Optional Google embeddings with a portable SQL-backed exact vector index."""
from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.models import UserMemory, UserMemoryEmbedding

logger = logging.getLogger(__name__)
MAX_INDEX_CANDIDATES = 500
MAX_SEMANTIC_RESULTS = 50
_EMBEDDING_PREFIX = "Represent this travel preference for semantic retrieval: "


def memory_fingerprint(memory: UserMemory) -> str:
    content = f"{memory.topic.strip()}\n{memory.text.strip()}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class GoogleMemoryEmbedder:
    """Uses the configured Google embedding API, never the chat model."""

    def __init__(self, api_key: str, model: str, dimensions: int, client=None):
        if dimensions < 1:
            raise ValueError("Embedding dimensions must be positive")
        self.model = model
        self.dimensions = dimensions
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self.client = client

    @classmethod
    def from_settings(cls):
        if not settings.google_api_key:
            return None
        return cls(
            settings.google_api_key,
            settings.google_embedding_model,
            settings.google_embedding_dimensions,
        )

    def embed(self, text: str) -> list[float]:
        from google.genai import types

        response = self.client.models.embed_content(
            model=self.model,
            contents=_EMBEDDING_PREFIX + text,
            config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
        )
        embeddings = getattr(response, "embeddings", None) or []
        values = getattr(embeddings[0], "values", None) if embeddings else None
        if not values or len(values) != self.dimensions:
            raise ValueError("Embedding provider returned an unexpected vector dimension")
        vector = [float(value) for value in values]
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("Embedding provider returned non-finite values")
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            raise ValueError("Embedding provider returned a zero vector")
        return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        raise ValueError("Embedding dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        raise ValueError("Cannot compare zero vectors")
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


class MemoryVectorIndex:
    """Stores derived vectors in the app database; relational memory owns status."""

    def __init__(self, embedder=None):
        self._embedder = embedder
        self._embedder_loaded = embedder is not None

    @property
    def embedder(self):
        if not self._embedder_loaded:
            self._embedder = GoogleMemoryEmbedder.from_settings()
            self._embedder_loaded = True
        return self._embedder

    def index_memory(self, db: Session, memory: UserMemory, force: bool = False) -> bool:
        embedder = self.embedder
        if embedder is None or memory.status != "active":
            return False
        fingerprint = memory_fingerprint(memory)
        existing = db.get(UserMemoryEmbedding, memory.memory_id)
        if (
            not force and existing and existing.model == embedder.model
            and existing.dimensions == embedder.dimensions
            and existing.fingerprint == fingerprint
        ):
            return False

        vector = embedder.embed(memory.text)
        if len(vector) != embedder.dimensions:
            raise ValueError("Embedding dimensions do not match configured dimensions")
        if existing is None:
            existing = UserMemoryEmbedding(memory_id=memory.memory_id)
            db.add(existing)
        existing.model = embedder.model
        existing.dimensions = len(vector)
        existing.fingerprint = fingerprint
        existing.vector_json = json.dumps(vector, separators=(",", ":"))
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True

    def remove_memory(self, db: Session, memory_id: str) -> None:
        vector = db.get(UserMemoryEmbedding, memory_id)
        if vector is not None:
            db.delete(vector)

    def semantic_scores(self, db: Session, user_id: str, tenant_id: str, query: str) -> dict[str, float]:
        embedder = self.embedder
        if embedder is None or not query.strip():
            return {}
        try:
            query_vector = embedder.embed(query)
            if len(query_vector) != embedder.dimensions:
                raise ValueError("Query embedding dimensions do not match configured dimensions")
            pairs = db.execute(
                select(UserMemory, UserMemoryEmbedding)
                .join(UserMemoryEmbedding, UserMemoryEmbedding.memory_id == UserMemory.memory_id)
                .where(
                    UserMemory.user_id == user_id,
                    UserMemory.tenant_id == tenant_id,
                    UserMemory.status == "active",
                    UserMemoryEmbedding.model == embedder.model,
                    UserMemoryEmbedding.dimensions == embedder.dimensions,
                )
                .order_by(UserMemory.updated_at.desc())
                .limit(MAX_INDEX_CANDIDATES)
            ).all()
            scores = {}
            for memory, stored in pairs:
                if stored.fingerprint != memory_fingerprint(memory):
                    continue
                vector = json.loads(stored.vector_json)
                if len(vector) != embedder.dimensions:
                    continue
                # Convert cosine [-1, 1] into normalized relevance [0, 1].
                relevance = (cosine_similarity(query_vector, vector) + 1.0) / 2.0
                # Avoid treating near-orthogonal memories as useful just because
                # cosine's normalized range has a midpoint of 0.5.
                if relevance >= 0.62:
                    scores[memory.memory_id] = relevance
            return dict(sorted(scores.items(), key=lambda item: item[1], reverse=True)[:MAX_SEMANTIC_RESULTS])
        except Exception as error:
            # Do not log the prompt, embedding values, API key, or provider response.
            logger.warning("Memory vector retrieval unavailable (%s)", type(error).__name__)
            return {}

