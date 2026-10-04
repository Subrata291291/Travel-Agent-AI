from app.llm.router import LLMRouter
from app.schemas.perception import TripPerception


class PerceptionAgent:

    def __init__(self, llm_router: LLMRouter):
        self.llm_router = llm_router

    def understand(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
    ) -> TripPerception:

        if conversation_history is None:
            conversation_history = []

        llm = self.llm_router.get_primary_llm()

        structured_llm = llm.with_structured_output(
            TripPerception,
            method="json_schema",
        )

        prompt = f"""
    You are the perception layer of a professional travel AI agent.

    Understand the user's current request using the
    conversation history when necessary.

    RULES:

    - Do not invent information.
    - Use conversation history to resolve references
    to previous messages.
    - If the user is answering a clarification question,
    combine the answer with the relevant previous context.
    - If the user says only a region, city, country, date,
    number, or other short answer, determine whether it
    refers to something discussed earlier.
    - Do not invent a year.
    - If a date is incomplete or ambiguous, keep it null.
    - Identify the primary intent.
    - Extract destination.
    - Extract dates only when the year is explicitly known.
    - Extract trip duration.
    - Extract number of travellers.
    - Extract budget and currency.
    - Extract important preferences and constraints.
    - Return only structured output.

    CONVERSATION HISTORY:

    {conversation_history}

    CURRENT USER MESSAGE:

    {user_message}
    """

        result = structured_llm.invoke(
            prompt
        )

        return result