from typing import Dict, List


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
    ) -> str:
        """
        Build a tenant-isolated key for in-memory conversation storage.

        The same session_id can safely exist under different tenants.
        """

        if not tenant_id:
            raise ValueError("tenant_id is required")

        if not session_id:
            raise ValueError("session_id is required")

        return f"{tenant_id}:{session_id}"
    

    def add_message(
        self,
        session_id: str,
        tenant_id: str,
        role: str,
        content: str,
    ) -> None:

        session_key = self._build_session_key(
            tenant_id,
            session_id,
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
    ) -> List[dict]:

        session_key = self._build_session_key(
            tenant_id,
            session_id,
        )

        return self.sessions.get(
            session_key,
            []
        )

    def clear_session(
        self,
        session_id: str,
        tenant_id: str,
    ) -> None:

        session_key = self._build_session_key(
            tenant_id,
            session_id,
        )

        self.sessions.pop(
            session_key,
            None
        )