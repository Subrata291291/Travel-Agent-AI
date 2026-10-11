"""Idempotently embed active relational user memories into the SQL vector sidecar."""
from __future__ import annotations

import argparse
import logging

from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models import UserMemory
from app.memory.long_term import LongTermMemory
from app.memory.vector_index import memory_fingerprint

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)
PAGE_SIZE = 100


def index_existing_memories(service: LongTermMemory | None = None) -> tuple[int, int]:
    service = service or LongTermMemory()
    db = SessionLocal()
    indexed = 0
    failures = 0
    last_id = ""
    try:
        while True:
            page = list(db.scalars(
                select(UserMemory)
                .where(UserMemory.status == "active", UserMemory.memory_id > last_id)
                .order_by(UserMemory.memory_id)
                .limit(PAGE_SIZE)
            ).all())
            if not page:
                break
            for memory in page:
                last_id = memory.memory_id
                existing = service.vector_index  # Uses configured model/dimensions.
                current_embedder = existing.embedder
                if current_embedder is None:
                    logger.warning("Embedding is not configured; indexed zero memories")
                    return indexed, failures + 1
                from app.database.models import UserMemoryEmbedding

                vector = db.get(UserMemoryEmbedding, memory.memory_id)
                if (
                    vector is not None
                    and vector.model == current_embedder.model
                    and vector.dimensions == current_embedder.dimensions
                    and vector.fingerprint == memory_fingerprint(memory)
                ):
                    continue
                try:
                    if service.index_memory(db, memory):
                        indexed += 1
                    else:
                        failures += 1
                except Exception as error:
                    # Continue the page; a later run resumes from any missing/stale rows.
                    db.rollback()
                    failures += 1
                    logger.warning("Could not index memory (%s)", type(error).__name__)
        return indexed, failures
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    indexed, failures = index_existing_memories()
    logger.info("Indexed %d memories; %d failures", indexed, failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
