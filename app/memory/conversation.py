from app.memory.short_term import ShortTermMemory
from app.memory.preferences import PreferenceMemory
from app.database.connection import SessionLocal
from app.database.repositories import WorkflowStateRepository
import json

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
    ):

        self.short_term.add_message(
            session_id,
            tenant_id,
            role,
            content,
        )

    def get_messages(
        self,
        session_id: str,
        tenant_id: str,
    ):

        return self.short_term.get_messages(
            session_id,
            tenant_id
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
                    tenant_id
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
                tenant_id
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

            repository.save_workflow_state(
                session_id=session_id,
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
    ):

        db = SessionLocal()

        try:

            repository = WorkflowStateRepository(db)

            workflow_state = (
                repository.get_workflow_state(
                    session_id,
                    tenant_id,
                )
            )

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
    ):

        db = SessionLocal()

        try:

            repository = WorkflowStateRepository(db)

            repository.delete_workflow_state(
                session_id,
                tenant_id,
            )

        finally:

            db.close()