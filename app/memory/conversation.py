from app.memory.short_term import ShortTermMemory
from app.memory.preferences import PreferenceMemory
from app.database.connection import SessionLocal
from app.database.repositories import WorkflowStateRepository
import json
import hashlib

class ConversationMemory:

    def __init__(self):

        self.short_term = (
            ShortTermMemory()
        )

        self.preferences = (
            PreferenceMemory()
        )

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
    ):

        self.short_term.add_message(
            session_id,
            tenant_id,
            role,
            content,
            user_id,
        )

    def get_messages(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str | None = None,
    ):

        return self.short_term.get_messages(
            session_id,
            tenant_id,
            user_id,
        )

    # ========================================================
    # User preferences
    # ========================================================

    def add_preference(
        self,
        user_id: str,
        preference: str,
    ):

        self.preferences.add_preference(
            user_id,
            preference,
        )

    def get_preferences(
        self,
        user_id: str,
    ):

        return self.preferences.get_preferences(
            user_id
        )

    # ========================================================
    # Conversation context
    # ========================================================

    def get_context(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ):

        context = {

            "conversation_history": (
                self.get_messages(
                    session_id,
                    tenant_id,
                    user_id,
                )
            ),

            "user_preferences": (
                self.get_preferences(
                    user_id
                )
            ),
        }

        workflow_state = (
            self.get_workflow_state(
                session_id,
                tenant_id,
                user_id,
            )
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
    ):

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

            db.close()

    def get_workflow_state(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str | None = None,
    ):

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

            db.close()

    def clear_workflow_state(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str | None = None,
    ):

        db = SessionLocal()

        try:

            repository = WorkflowStateRepository(db)

            owned_session_id = self._owned_session_id(session_id, user_id)

            repository.delete_workflow_state(
                owned_session_id,
                tenant_id,
            )

        finally:

            db.close()

    @staticmethod
    def _owned_session_id(session_id: str, user_id: str | None) -> str:
        return hashlib.sha256(
            f"{user_id or 'legacy'}:{session_id}".encode("utf-8")
        ).hexdigest()
