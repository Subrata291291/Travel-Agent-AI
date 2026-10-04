from app.memory.short_term import ShortTermMemory
from app.memory.preferences import PreferenceMemory


class ConversationMemory:

    def __init__(self):

        self.short_term = (
            ShortTermMemory()
        )

        self.preferences = (
            PreferenceMemory()
        )

        self.workflow_states = {}

    # ========================================================
    # Conversation messages
    # ========================================================

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ):

        self.short_term.add_message(
            session_id,
            role,
            content,
        )

    def get_messages(
        self,
        session_id: str,
    ):

        return self.short_term.get_messages(
            session_id
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
        user_id: str,
    ):

        context = {

            "conversation_history": (
                self.get_messages(
                    session_id
                )
            ),

            "user_preferences": (
                self.get_preferences(
                    user_id
                )
            ),
        }

        workflow_state = (
            self.workflow_states.get(
                session_id,
                {}
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
        state: dict,
    ):

        self.workflow_states[
            session_id
        ] = state

    def get_workflow_state(
        self,
        session_id: str,
    ):

        return self.workflow_states.get(
            session_id,
            {}
        )

    def clear_workflow_state(
        self,
        session_id: str,
    ):

        self.workflow_states.pop(
            session_id,
            None
        )