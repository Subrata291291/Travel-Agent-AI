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
            method="json_mode",
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
    - For requests to find, show, compare, or consider transportation options,
    always set intent to "find_transport".
    - Never use "compare_transport" as an intent.
    - Use transport_mode = "any" when the user wants flight, train, and bus options.
    Identify the primary intent.

    TRANSPORT MODE RULES:

    - If the user explicitly requests a flight,
    set transport_mode to "flight".

    - If the user explicitly requests a train,
    set transport_mode to "train".

    - If the user explicitly requests a bus,
    set transport_mode to "bus".

    - If the user asks to see, compare, or consider
    all transportation modes, set transport_mode to "any".

    - If the user does not specify a transportation mode,
    set transport_mode to "unknown".

    - Never assume flight, train, or bus when the user
    has not specified a transportation preference.

    - If the user expresses a transportation preference
    such as "I prefer train", use that mode.

    - If the user changes their transportation preference
    during the conversation, use the user's latest
    explicit preference for the current request.

    - If the user does not specify a currency, use "INR".
    - Never return null for currency when no currency is explicitly provided.

    Return ONLY a valid JSON object.

    The JSON object must contain exactly these fields:

    - intent
    - destination
    - start_date
    - end_date
    - duration_days
    - travellers
    - budget
    - currency
    - preferences
    - transport_mode

    Rules for JSON:
    - Do not wrap the JSON in markdown.
    - Do not add explanations before or after the JSON.
    - If a value is unknown, use null where the schema allows it.
    - Use "INR" for currency when the user does not specify a currency.
    - transport_mode must be one of:
    "flight", "train", "bus", "any", "unknown".

    CONVERSATION HISTORY:

    {conversation_history}

    CURRENT USER MESSAGE:

    {user_message}
    """

        result = structured_llm.invoke(
            prompt
        )

        return result