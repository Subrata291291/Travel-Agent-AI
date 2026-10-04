from typing import Dict, List


class PreferenceMemory:
    """
    Stores long-term travel preferences for users.
    """

    def __init__(self):
        self.preferences: Dict[str, List[str]] = {}

    def add_preference(
        self,
        user_id: str,
        preference: str,
    ) -> None:

        if user_id not in self.preferences:
            self.preferences[user_id] = []

        if preference not in self.preferences[user_id]:
            self.preferences[user_id].append(
                preference
            )

    def get_preferences(
        self,
        user_id: str,
    ) -> List[str]:

        return self.preferences.get(
            user_id,
            []
        )

    def remove_preference(
        self,
        user_id: str,
        preference: str,
    ) -> None:

        if user_id not in self.preferences:
            return

        if preference in self.preferences[user_id]:
            self.preferences[user_id].remove(
                preference
            )

    def clear_preferences(
        self,
        user_id: str,
    ) -> None:

        self.preferences.pop(
            user_id,
            None
        )