from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.tenant_context import TenantContext
from app.database.connection import get_db
from app.database.models import UserMemory
from app.memory.long_term import LongTermMemory, contains_sensitive_information

router = APIRouter(prefix="/memories", tags=["Memory"])


class MemoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=3, max_length=500)

    @field_validator("text")
    @classmethod
    def validate_memory_text(cls, value: str) -> str:
        value = value.strip()
        if contains_sensitive_information(value):
            raise ValueError("Sensitive information cannot be saved as memory")
        return value


@router.get("")
def list_memories(context: TenantContext = Depends(get_current_user), db: Session = Depends(get_db)):
    items = LongTermMemory().list(db, context.user_id, context.tenant_id)
    return {"memories": [_serialize(item) for item in items]}


@router.patch("/{memory_id}")
def update_memory(memory_id: str, request: MemoryUpdate,
                  context: TenantContext = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(UserMemory).where(
        UserMemory.memory_id == memory_id,
        UserMemory.user_id == context.user_id,
        UserMemory.tenant_id == context.tenant_id,
        UserMemory.status == "active",
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Memory not found.")
    item.text = request.text.strip()
    item.source_quote = "Updated by the user in memory settings."
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    LongTermMemory().index_memory(db, item)
    return _serialize(item)


@router.delete("/{memory_id}", status_code=204)
def delete_memory(memory_id: str, context: TenantContext = Depends(get_current_user), db: Session = Depends(get_db)):
    if not LongTermMemory().delete(db, context.user_id, context.tenant_id, memory_id):
        raise HTTPException(status_code=404, detail="Memory not found.")


@router.delete("", status_code=200)
def clear_memories(context: TenantContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"deleted": LongTermMemory().clear(db, context.user_id, context.tenant_id)}


def _serialize(item: UserMemory):
    return {
        "memory_id": item.memory_id,
        "text": item.text,
        "topic": item.topic,
        "kind": item.kind,
        "importance": item.importance,
        "confidence": item.confidence,
        "source_quote": item.source_quote,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
