from typing import Dict, List
import hashlib

from sqlalchemy import select

from app.database.models import ConversationMessage


class ShortTermMemory:
    """
    Stores conversation history for the current session.
    """

    def __init__(self):
        self.sessions: Dict[str, List[dict]] = {}

    def _build_session_key(
        self,
        tenant_id: str,
        session_id: str,
        user_id: str | None = None,
    ) -> str:
        """
        Build a tenant-isolated key for in-memory conversation storage.

        The same session_id can safely exist under different tenants.
        """

        if not tenant_id:
            raise ValueError("tenant_id is required")

        if not session_id:
            raise ValueError("session_id is required")

        return f"{tenant_id}:{user_id or 'legacy'}:{session_id}"
    

    def add_message(
        self,
        session_id: str,
        tenant_id: str,
        role: str,
        content: str,
        user_id: str | None = None,
        db=None,
    ) -> None:

        if db is not None:
            if not user_id:
                raise ValueError("user_id is required for persistent conversation history")
            db.add(ConversationMessage(
                tenant_id=tenant_id,
                user_id=user_id,
                session_key=self._persistent_session_key(session_id, user_id),
                role=role,
                content=content,
            ))
            db.commit()
            return

        session_key = self._build_session_key(
            tenant_id,
            session_id,
            user_id,
        )

        if session_key not in self.sessions:
            self.sessions[session_key] = []

        self.sessions[session_key].append(
            {
                "role": role,
                "content": content,
            }
        )

    def get_messages(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str | None = None,
        db=None,
    ) -> List[dict]:

        if db is not None:
            if not user_id:
                return []
            rows = db.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.tenant_id == tenant_id,
                    ConversationMessage.user_id == user_id,
                    ConversationMessage.session_key == self._persistent_session_key(session_id, user_id),
                )
                .order_by(ConversationMessage.message_id.desc())
                .limit(100)
            ).all()
            return [
                {"role": item.role, "content": item.content}
                for item in reversed(rows)
            ]

        session_key = self._build_session_key(
            tenant_id,
            session_id,
            user_id,
        )

        return self.sessions.get(
            session_key,
            []
        )

    @staticmethod
    def _persistent_session_key(session_id: str, user_id: str) -> str:
        return hashlib.sha256(f"{user_id}:{session_id}".encode("utf-8")).hexdigest()

    def clear_session(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str | None = None,
    ) -> None:

        session_key = self._build_session_key(
            tenant_id,
            session_id,
            user_id,
        )

        self.sessions.pop(
            session_key,
            None
        )
