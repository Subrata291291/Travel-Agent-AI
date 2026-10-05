from app.llm.router import LLMRouter
from app.schemas.perception import TripPerception


class PerceptionAgent:
    """
    Perception Agent

    This layer understands what the user is asking for and converts
    the natural-language request into structured TripPerception data.

    Example:

        User:
            "I want to go to Manali with my wife on 20 December."

        Output:
            intent = find_transport / plan_trip
            destination = Manali
            travellers = 2
            start_date = 2026-12-20
            etc.

    Important:

    This agent does NOT perform the actual booking.

    It only understands the user's request.

    For booking conversations, it can also detect whether the
    user explicitly confirmed or rejected a pending booking.
    """

    # ------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------

    def __init__(self, llm_router: LLMRouter):
        """
        Initialize the perception agent with the shared LLM router.

        The router is responsible for selecting the primary LLM
        and falling back to other providers when necessary.
        """

        self.llm_router = llm_router

    # ------------------------------------------------------------------
    # DETERMINISTIC APPLICATION-LEVEL INTENT DETECTION
    # ------------------------------------------------------------------

    def _is_get_bookings_request(self, user_message: str) -> bool:
        """
        Detect requests to retrieve the current user's bookings.

        This detection is intentionally deterministic.

        Why?

        Retrieving a user's own booking history is an application-level
        command. It should not depend entirely on probabilistic LLM
        classification.

        Example messages:

            "Show my bookings"
            "Show my booking"
            "List my bookings"
            "View my bookings"
            "See my bookings"
            "Get my bookings"
            "Show my booking history"
            "Can you show my previous bookings?"
            "Do I have any bookings?"

        If one of these patterns is detected, the perception layer
        directly returns intent = "get_bookings".
        """

        text = user_message.strip().lower()

        booking_history_phrases = [
            "show my bookings",
            "show my booking",
            "list my bookings",
            "list my booking",
            "view my bookings",
            "view my booking",
            "see my bookings",
            "see my booking",
            "get my bookings",
            "get my booking",
            "my bookings",
            "my booking history",
            "booking history",
            "show previous bookings",
            "show previous booking",
            "show my previous bookings",
            "show my previous booking",
            "show my travel bookings",
            "do i have any bookings",
            "do i have any booking",
            "what are my bookings",
            "what are my booking",
        ]

        return any(
            phrase in text
            for phrase in booking_history_phrases
        )

    # ------------------------------------------------------------------
    # MAIN PERCEPTION METHOD
    # ------------------------------------------------------------------

    def understand(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
    ) -> TripPerception:
        """
        Understand the user's current message and convert it into
        a structured TripPerception object.

        Conversation history is provided so that short follow-up
        messages such as:

            "Himachal Pradesh"
            "Book TRAIN-1"
            "Yes, book it"

        can be understood using previous conversation context.
        """

        # If there is no previous conversation, use an empty list.
        if conversation_history is None:
            conversation_history = []

        # ==============================================================
        # IMPORTANT:
        # DETERMINISTIC BOOKING HISTORY DETECTION
        # ==============================================================

        # Retrieving existing bookings is an application-level action.
        #
        # We do NOT want the LLM to randomly classify:
        #
        #     "Show my bookings"
        #
        # as:
        #
        #     "question"
        #
        # or:
        #
        #     "other"
        #
        # Therefore we detect it before calling the LLM.
        if self._is_get_bookings_request(user_message):
            return TripPerception(
                intent="get_bookings",
                destination=None,
                start_date=None,
                end_date=None,
                duration_days=None,
                travellers=1,
                budget=None,
                currency="INR",
                preferences=[],
                transport_mode="unknown",
                selected_option_id=None,
                confirmation="unknown",
            )

        # ==============================================================
        # LLM-BASED PERCEPTION
        # ==============================================================

        prompt = f"""
You are the perception layer of a professional travel AI agent.

Your job is to understand the user's CURRENT request and convert
it into a structured travel request.

Use the conversation history when necessary to understand
follow-up messages and references to previously discussed
information.

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


INTENT RULES:

Use ONLY one of these intents:

- "plan_trip"
- "check_weather"
- "find_transport"
- "find_hotel"
- "find_restaurant"
- "book_trip"
- "get_bookings"
- "question"
- "other"


BOOKING HISTORY / MY BOOKINGS RULES:

- If the user asks to see, show, list, view, retrieve, or check
  their existing bookings, set intent to "get_bookings".

Examples:

User:
"Show my bookings"

User:
"Show my bookings please"

User:
"List my bookings"

User:
"What are my bookings?"

User:
"View my bookings"

User:
"Can you show my previous bookings?"

User:
"Do I have any bookings?"

User:
"Show my travel bookings"

In all of these cases:

intent = "get_bookings"

The user is asking to retrieve existing bookings.

Do not interpret this as "question".

For "get_bookings":

- destination = null
- start_date = null
- end_date = null
- duration_days = null
- travellers = 1
- budget = null
- currency = "INR"
- preferences = []
- transport_mode = "unknown"
- selected_option_id = null
- confirmation = "unknown"

IMPORTANT:

"get_bookings" means retrieving existing bookings.

It does NOT mean creating a new booking.

Never set intent = "book_trip" merely because the user
mentions the word "booking" or "bookings".


TRANSPORT SEARCH RULES:

- For requests to find, show, compare, or consider
  transportation options, always set intent to
  "find_transport".

- Never use "compare_transport" as an intent.

- Use transport_mode = "any" when the user wants
  flight, train, and bus options.

- If the user explicitly requests a flight,
  set transport_mode to "flight".

- If the user explicitly requests a train,
  set transport_mode to "train".

- If the user explicitly requests a bus,
  set transport_mode to "bus".

- If the user asks to see, compare, or consider
  all transportation modes, set transport_mode
  to "any".

- If the user does not specify a transportation mode,
  set transport_mode to "unknown".

- Never assume flight, train, or bus when the user
  has not specified a transportation preference.

- If the user expresses a transportation preference
  such as "I prefer train", use that mode.

- If the user changes their transportation preference
  during the conversation, use the user's latest
  explicit preference for the current request.


TRANSPORT BOOKING / SELECTION RULES:

If the user wants to book a previously displayed
transport option:

- Set intent = "book_trip".

- Extract the exact selected option ID.

- Preserve the exact option ID.

- Do not invent the option ID.

- Do not modify the option ID.

- Do not normalize the option ID.

Valid option IDs may look like:

- FLIGHT-1
- TRAIN-1
- BUS-1


Examples:

User:

"Book TRAIN-1"

Output:

intent = "book_trip"
selected_option_id = "TRAIN-1"


User:

"I want FLIGHT-1"

Output:

intent = "book_trip"
selected_option_id = "FLIGHT-1"


User:

"Book BUS-1"

Output:

intent = "book_trip"
selected_option_id = "BUS-1"


IMPORTANT:

Do not claim that the option has been booked.

The perception layer only identifies:

1. The user's booking intent.
2. The selected option ID.
3. Whether the user explicitly confirmed or rejected
   a pending booking.


OPTION ID RULES:

- If the user selects a previously displayed transport
  option, preserve the exact option ID from the conversation.

- If the user mentions an exact option ID such as
  FLIGHT-1, TRAIN-1, or BUS-1, treat it as the
  selected transport option.

- Do not confuse the option ID with the transport mode.

- Do not invent an option ID.

- If the user is not selecting a transport option,
  selected_option_id must be null.


BOOKING CONFIRMATION RULES:

The system may ask the user to confirm a booking
before the actual booking is executed.

You must detect the user's explicit confirmation
status.

Use ONLY these values:

- "yes"
- "no"
- "unknown"


Use confirmation = "yes" when the user clearly
confirms the pending booking.

Examples:

User:
"Yes"

User:
"Yes, book it"

User:
"Confirm"

User:
"Go ahead"

User:
"Proceed with the booking"

User:
"Yes, I want to book it"

In these cases:

confirmation = "yes"


Use confirmation = "no" when the user clearly
rejects, cancels, or does not want the pending
booking.

Examples:

User:
"No"

User:
"No, don't book it"

User:
"Cancel"

User:
"I don't want it"

User:
"Don't book"

In these cases:

confirmation = "no"


Use confirmation = "unknown" when the user has
not clearly confirmed or rejected the booking.

Examples:

User:
"Which one is better?"

User:
"How much is it?"

User:
"Tell me the departure time."

User:
"I am not sure."

User:
"Book TRAIN-1"

The last example is important.

"Book TRAIN-1" selects the option, but the system
must still ask for explicit confirmation before
executing the actual booking.

Therefore:

confirmation = "unknown"


IMPORTANT BOOKING SAFETY RULE:

Never interpret an ambiguous message as confirmation.

Only use confirmation = "yes" when the user's
message clearly and explicitly confirms the pending
booking.

Never assume that words such as:

- okay
- fine
- sounds good
- maybe
- I think so

mean booking confirmation unless the context makes
the confirmation explicit.

The actual booking is handled by another part of
the application.

This perception layer must NEVER claim that a booking
has been completed.


CURRENCY RULES:

- If the user specifies a currency, preserve it.

- If the user does not specify a currency,
  use "INR".

- Never return null for currency when no currency
  was explicitly provided.


TRAVELLER RULES:

- Extract the number of travellers when explicitly
  provided.

- If the number is not provided, use 1.

- Do not invent a different number of travellers.


DATE RULES:

- Extract a date only when the year is explicitly known.

- Use YYYY-MM-DD format.

- Do not invent a year.

- If the date is incomplete or ambiguous,
  return null.

- Use conversation history if the year was explicitly
  established earlier in the conversation.


PREFERENCE RULES:

- Extract meaningful travel preferences and constraints.

Examples:

- budget travel
- luxury
- family friendly
- vegetarian
- near airport
- train preferred
- avoid buses

- If no preferences exist, return an empty list when possible.

- Do not invent preferences.


CONVERSATION CONTEXT:

The previous conversation is:

{conversation_history}


CURRENT USER MESSAGE:

{user_message}


OUTPUT RULES:

Return ONLY a valid JSON object.

Do not return markdown.

Do not return explanations.

Do not return text before or after the JSON.

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
- selected_option_id
- confirmation


FIELD RULES:

intent must be one of:

- "plan_trip"
- "check_weather"
- "find_transport"
- "find_hotel"
- "find_restaurant"
- "book_trip"
- "get_bookings"
- "question"
- "other"


transport_mode must be one of:

- "flight"
- "train"
- "bus"
- "any"
- "unknown"


selected_option_id:

- Must be null when no previously displayed
  transport option was selected.

- Must contain the exact option ID when the user
  selects a previously displayed transport option.

- Never invent an option ID.


confirmation must be one of:

- "yes"
- "no"
- "unknown"

Use "yes" only for explicit booking confirmation.

Use "no" only for explicit rejection or cancellation.

Use "unknown" when there is no clear confirmation.


UNKNOWN VALUES:

- Use null only for fields where the schema allows null.

- travellers must NEVER be null.
  Use 1 when the number of travellers is not provided.

- currency must NEVER be null.
  Use "INR" when the user does not specify another currency.

- preferences should be [] when no preferences are provided.

- transport_mode should be "unknown" when no transport mode
  is specified.

- confirmation should be "unknown" when there is no explicit
  booking confirmation or rejection.

Currency:

- Use "INR" when the user does not specify
  another currency.
"""

        # ==============================================================
        # STRUCTURED LLM CALL
        # ==============================================================

        # Ask the LLM router to generate structured output.
        #
        # IMPORTANT:
        #
        # We intentionally do NOT call get_primary_llm() here.
        #
        # invoke_structured() handles provider fallback:
        #
        # Groq
        #   ↓ failure
        # OpenRouter
        #   ↓ failure
        # Gemini
        #   ↓ failure
        # OpenAI
        #
        # This means a Groq 401/429 error does not
        # automatically stop the perception layer.

        result = self.llm_router.invoke_structured(
            prompt,
            TripPerception,
        )

        return result