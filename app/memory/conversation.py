from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.database.connection import SessionLocal
from app.database.repositories import WorkflowStateRepository
import json
import hashlib

class ConversationMemory:

    def __init__(self, llm_router=None):

        self.short_term = (
            ShortTermMemory()
        )

        self.preferences = LongTermMemory(llm_router)

    # ========================================================
    # Conversation messages
    # ========================================================

    def add_message(
        self,
        session_id: str,
        tenant_id: str,
        role: str,
        content: str,
        user_id: str | None = None,
        db=None,
    ):

        self.short_term.add_message(
            session_id,
            tenant_id,
            role,
            content,
            user_id,
            db,
        )

    def get_messages(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str | None = None,
        db=None,
    ):

        return self.short_term.get_messages(
            session_id,
            tenant_id,
            user_id,
            db,
        )

    # ========================================================
    # User preferences
    # ========================================================

    def add_preference(self, user_id: str, preference: str):
        """Legacy in-memory preference writes are intentionally no longer used."""
        return None

    # ========================================================
    # Conversation context
    # ========================================================

    def get_context(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        query: str = "",
        db=None,
    ):

        context = {

            "conversation_history": (
                self.get_messages(
                    session_id,
                    tenant_id,
                    user_id,
                    db,
                )
            ),

            "user_preferences": [],
        }

        if db is not None and tenant_id:
            context["user_preferences"] = [
                {"text": memory.text, "topic": memory.topic}
                for memory, _score in self.preferences.retrieve(
                    db, user_id, tenant_id, query, limit=5
                )
            ]

        workflow_state = self.get_workflow_state(
            session_id, tenant_id, user_id, db=db
        )

        context.update(
            workflow_state
        )

        return context

    # ========================================================
    # Workflow state
    # ========================================================

    def save_workflow_state(
        self,
        session_id: str,
        user_id: str,
        tenant_id: str,
        state: dict,
        db=None,
    ):

        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        try:

            repository = WorkflowStateRepository(db)

            owned_session_id = self._owned_session_id(session_id, user_id)

            repository.save_workflow_state(
                session_id=owned_session_id,
                user_id=user_id,
                tenant_id=tenant_id,
                state=json.dumps(state, default=str),
            )

        finally:

            if owns_db:
                db.close()

    def get_workflow_state(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str | None = None,
        db=None,
    ):

        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        try:

            repository = WorkflowStateRepository(db)

            owned_session_id = self._owned_session_id(session_id, user_id)

            workflow_state = (
                repository.get_workflow_state(
                    owned_session_id,
                    tenant_id,
                )
            )

            # Read legacy rows created before user-scoped session keys, but
            # only when their recorded owner matches the authenticated user.
            if not workflow_state:
                legacy_state = repository.get_workflow_state(
                    session_id,
                    tenant_id,
                )
                if legacy_state and legacy_state.user_id == user_id:
                    workflow_state = legacy_state

            if not workflow_state:
                return {}

            return json.loads(
                workflow_state.state
            )

        finally:

            if owns_db:
                db.close()

    def clear_workflow_state(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str | None = None,
        db=None,
    ):

        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        try:

            repository = WorkflowStateRepository(db)

            owned_session_id = self._owned_session_id(session_id, user_id)

            repository.delete_workflow_state(
                owned_session_id,
                tenant_id,
            )

        finally:

            if owns_db:
                db.close()

    @staticmethod
    def _owned_session_id(session_id: str, user_id: str | None) -> str:
        return hashlib.sha256(
            f"{user_id or 'legacy'}:{session_id}".encode("utf-8")
        ).hexdigest()
