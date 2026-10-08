from app.llm.router import LLMRouter
from app.schemas.perception import TripPerception
import re


class PerceptionAgent:
    """
    Perception Agent

    This layer understands what the user is asking for and converts
    the natural-language request into structured TripPerception data.

    Important:

    This agent does NOT perform booking or cancellation.

    It only understands the user's request and produces structured
    data for the application workflow.
    """

    # ==============================================================
    # INITIALIZATION
    # ==============================================================

    def __init__(self, llm_router: LLMRouter):
        """
        Initialize the perception agent with the shared LLM router.

        The router is responsible for selecting the primary LLM
        and falling back to other providers when necessary.
        """

        self.llm_router = llm_router

    # ==============================================================
    # DETERMINISTIC: GET BOOKINGS
    # ==============================================================

    def _is_get_bookings_request(self, user_message: str) -> bool:
        """
        Detect requests to retrieve the user's existing bookings.

        This is intentionally deterministic because retrieving a
        user's own booking history is an application-level command.

        We should not depend completely on probabilistic LLM
        classification for this type of operation.
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

            # Hotel booking history
            "show my hotel bookings",
            "show my hotel booking",
            "list my hotel bookings",
            "list my hotel booking",
            "view my hotel bookings",
            "view my hotel booking",
            "see my hotel bookings",
            "see my hotel booking",
            "get my hotel bookings",
            "get my hotel booking",
            "my hotel bookings",
            "my hotel booking history",

            # Transport booking history
            "show my train bookings",
            "show my train booking",
            "show my flight bookings",
            "show my flight booking",
            "show my bus bookings",
            "show my bus booking",
            "show my transport bookings",
            "show my transport booking",

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


    def _is_get_booking_details_request(
        self,
        user_message: str,
    ) -> bool:
        """
        Detect whether the user wants details of
        one specific existing booking.

        This is deterministic because booking IDs are
        structured identifiers and should not depend
        on LLM interpretation.
        """

        text = user_message.strip().lower()

        booking_id = self._extract_booking_id(
            user_message
        )

        if not booking_id:
            return False

        detail_phrases = [
            "show details",
            "show detail",
            "booking details",
            "booking detail",
            "details of",
            "detail of",
            "view details",
            "view detail",
            "get details",
            "get detail",
        ]

        return any(
            phrase in text
            for phrase in detail_phrases
        )

    @staticmethod
    def _is_hotel_recommendation_request(
        user_message: str,
        conversation_history: list[dict],
    ) -> bool:
        """Recognize hotel recommendation requests deterministically."""

        if re.search(r"\bHOTEL-\d+\b", user_message.upper()):
            return False

        text = re.sub(
            r"[^a-z0-9\s-]",
            " ",
            user_message.lower(),
        )
        mentions_hotel = re.search(
            r"\b(hotels?|resorts?|accommodation|stays?)\b",
            text,
        )
        asks_recommendation = re.search(
            r"\b(recommend\w*|suggest\w*|best|choose)\b",
            text,
        )
        if mentions_hotel and asks_recommendation:
            return True

        # Contextual references such as "Which one should I choose?"
        # apply only when a prior assistant response actually listed hotels.
        if re.search(r"\b(which one|what one)\b.*\b(choose|pick|select)\b", text):
            for message in conversation_history:
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    continue
                content = str(message.get("content", "")).lower()
                if "available hotel options:" in content and "hotel id:" in content:
                    return True

        return False

    @staticmethod
    def _hotel_option_selection(user_message: str) -> str | None:
        """Extract a hotel ID only when the user explicitly selects it."""

        match = re.search(r"\bHOTEL-\d+\b", user_message.upper())
        if not match:
            return None
        if re.search(r"\b(book|choose|select|pick|go with|take)\b", user_message.lower()):
            return match.group(0)
        return None
    
    # ==============================================================
    # DETERMINISTIC: BOOKING DOMAIN
    # ==============================================================

    def _detect_booking_domain(
        self,
        user_message: str,
    ) -> str:
        """
        Detect which booking domain the user is referring to.

        Returns:
            "hotel"      -> hotel/resort/accommodation bookings
            "transport"  -> train/flight/bus bookings
            "unknown"    -> no specific booking domain mentioned

        This is deterministic application logic because the
        booking retrieval domain should be predictable.
        """

        text = user_message.strip().lower()

        # ----------------------------------------------------------
        # HOTEL
        # ----------------------------------------------------------

        hotel_keywords = [
            "hotel",
            "hotels",
            "resort",
            "resorts",
            "accommodation",
            "stay",
            "room",
            "rooms",
        ]

        if any(
            keyword in text
            for keyword in hotel_keywords
        ):
            return "hotel"

        # ----------------------------------------------------------
        # TRANSPORT
        # ----------------------------------------------------------

        transport_keywords = [
            "train",
            "trains",
            "flight",
            "flights",
            "bus",
            "buses",
            "transport",
            "railway",
        ]

        if any(
            keyword in text
            for keyword in transport_keywords
        ):
            return "transport"

        # ----------------------------------------------------------
        # UNKNOWN
        # ----------------------------------------------------------

        return "unknown"
    
    # ==============================================================
    # DETERMINISTIC: CANCEL BOOKING
    # ==============================================================

    def _extract_booking_id(self, user_message: str) -> str | None:
        """
        Extract a booking ID from the user's message.

        Expected booking ID format:

            BOOK-29F06E436FF9

        We intentionally keep this simple and strict.

        The booking ID must:

            - start with BOOK-
            - contain the remaining identifier
            - preserve the exact value

        Returns:
            Exact booking ID if found.
            None otherwise.
        """

        import re

        match = re.search(
            r"\bBOOK-[A-Z0-9]+\b",
            user_message.upper(),
        )

        if not match:
            return None

        return match.group(0)

    def _is_cancel_booking_request(self, user_message: str) -> bool:
        """
        Detect whether the user is asking to cancel an existing booking.

        This is deterministic because cancellation is an application
        action with real consequences.

        Examples:

            "Cancel BOOK-29F06E436FF9"
            "I want to cancel BOOK-29F06E436FF9"
            "Please cancel my booking BOOK-29F06E436FF9"
            "Cancel my booking"
        """

        text = user_message.strip().lower()

        # A booking ID makes the short imperative "Cancel BOOK-…"
        # an unambiguous cancellation request, even without "my booking".
        if (
            text.startswith("cancel ")
            and self._extract_booking_id(user_message)
        ):
            return True

        cancellation_phrases = [
            "cancel booking",
            "cancel my booking",
            "cancel the booking",
            "cancel this booking",
            "cancel my reservation",
            "cancel reservation",
            "cancel this reservation",
            "i want to cancel",
            "i need to cancel",
            "please cancel",
            "can you cancel",
        ]

        return any(
            phrase in text
            for phrase in cancellation_phrases
        )

    # ==============================================================
    # MAIN PERCEPTION METHOD
    # ==============================================================

    def understand(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
    ) -> TripPerception:
        """
        Understand the user's current message and convert it into
        a structured TripPerception object.

        Conversation history is provided so that short follow-up
        messages can be understood using previous context.
        """

        # ----------------------------------------------------------
        # DEFAULT CONVERSATION HISTORY
        # ----------------------------------------------------------

        if conversation_history is None:
            conversation_history = []

        selected_hotel_id = self._hotel_option_selection(user_message)
        if selected_hotel_id:
            return TripPerception(
                intent="book_trip",
                selected_option_id=selected_hotel_id,
                booking_domain="hotel",
            )

        if self._is_hotel_recommendation_request(
            user_message,
            conversation_history,
        ):
            return TripPerception(intent="recommend_hotel")
        
                # ==========================================================
        # APPLICATION-LEVEL: GET BOOKING DETAILS
        # ==========================================================

        if self._is_get_booking_details_request(
            user_message
        ):

            booking_id = self._extract_booking_id(
                user_message
            )

            booking_domain = self._detect_booking_domain(
                user_message
            )

            return TripPerception(
                intent="get_booking_details",
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
                booking_id=booking_id,
                booking_domain=booking_domain,
                confirmation="unknown",
            )

        # ==========================================================
        # APPLICATION-LEVEL: GET BOOKINGS
        # ==========================================================

        if self._is_get_bookings_request(user_message):

            booking_domain = self._detect_booking_domain(
                user_message
            )

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
                booking_id=None,
                booking_domain=booking_domain,
                confirmation="unknown",
            )

        # ==========================================================
        # APPLICATION-LEVEL: CANCEL BOOKING
        # ==========================================================

        booking_id = self._extract_booking_id(user_message)

        if self._is_cancel_booking_request(user_message):

            return TripPerception(
                intent="cancel_booking",
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
                booking_id=booking_id,
                confirmation="unknown",
            )

        # ==========================================================
        # LLM-BASED PERCEPTION
        # ==========================================================

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
- "recommend_hotel"
- "find_restaurant"
- "book_trip"
- "get_bookings"
- "cancel_booking"
- "question"
- "other"

Use "recommend_hotel" when the user asks which hotel is best,
which hotel you recommend, or asks you to suggest a hotel. If the
user says "which one should I choose?", use this intent when the
conversation history shows a hotel options list.


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
- booking_id = null
- confirmation = "unknown"

IMPORTANT:

"get_bookings" means retrieving existing bookings.

It does NOT mean creating a new booking.


CANCEL BOOKING RULES:

If the user wants to cancel an existing booking:

- Set intent = "cancel_booking".

- Extract the exact booking ID when provided.

- Store the booking ID in booking_id.

- Preserve the exact booking ID.

- Do not confuse booking_id with selected_option_id.

- Do not invent a booking ID.

Examples:

User:
"Cancel BOOK-29F06E436FF9"

Output:

intent = "cancel_booking"
booking_id = "BOOK-29F06E436FF9"


User:
"I want to cancel my booking BOOK-29F06E436FF9"

Output:

intent = "cancel_booking"
booking_id = "BOOK-29F06E436FF9"


User:
"Please cancel BOOK-29F06E436FF9"

Output:

intent = "cancel_booking"
booking_id = "BOOK-29F06E436FF9"


IMPORTANT:

The perception layer does NOT cancel the booking.

It only identifies the cancellation request.

Never claim that the booking has already been cancelled.

If the user asks to cancel a booking but does not provide
a booking ID, keep booking_id = null and let the application
handle clarification.


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

        # ==========================================================
        # HOTEL BOOKING / SELECTION RULES
        # ==========================================================

        HOTEL BOOKING RULES:

        If the user wants to book a previously displayed hotel option:

        - Set intent = "book_trip".
        - Extract the exact selected hotel option ID.
        - Preserve the exact option ID.
        - Do not invent the option ID.
        - Do not modify the option ID.
        - Do not normalize the option ID.

        Valid hotel option IDs may look like:

        - HOTEL-1
        - HOTEL-2
        - HOTEL-3

        Examples:

        User:

        "Book HOTEL-1"

        Output:

        intent = "book_trip"
        selected_option_id = "HOTEL-1"


        User:

        "Book HOTEL-2"

        Output:

        intent = "book_trip"
        selected_option_id = "HOTEL-2"


        User:

        "I want to book HOTEL-3"

        Output:

        intent = "book_trip"
        selected_option_id = "HOTEL-3"


        IMPORTANT:

        If the user selects a previously displayed hotel option,
        selected_option_id must contain the exact hotel option ID.

        Do not confuse selected_option_id with booking_id.

        HOTEL-2 is a hotel option ID.

        BOOK-XXXXXXXXXXXX is an existing booking ID.


  
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

- HOTEL-1
- HOTEL-2
- HOTEL-3
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
HOTEL-1, HOTEL-2, HOTEL-3, FLIGHT-1, TRAIN-1, or BUS-1,
treat it as the selected option.

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
- booking_id
- confirmation


FIELD RULES:

intent must be one of:

- "plan_trip"
- "check_weather"
- "find_transport"
- "find_hotel"
- "recommend_hotel"
- "find_restaurant"
- "book_trip"
- "get_bookings"
- "cancel_booking"
- "question"
- "other"

"recommend_hotel" is a hotel recommendation request, not a hotel
booking request. Do not set selected_option_id unless the user
explicitly selects a hotel.


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


booking_id:

- Must be null when the user is not referring
  to an existing booking.

- Must contain the exact booking ID when the user
  refers to an existing booking.

- Never invent a booking ID.

- Never confuse booking_id with selected_option_id.


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

- selected_option_id should be null when no transport option
  is selected.

- booking_id should be null when no existing booking
  is referenced.

- confirmation should be "unknown" when there is no explicit
  booking confirmation or rejection.

Currency:

- Use "INR" when the user does not specify
  another currency.
"""

        # ==========================================================
        # STRUCTURED LLM CALL
        # ==========================================================

        # invoke_structured() is responsible for provider fallback:
        #
        # Groq
        #   ↓ failure
        # OpenRouter
        #   ↓ failure
        # Gemini
        #   ↓ failure
        # OpenAI

        result = self.llm_router.invoke_structured(
            prompt,
            TripPerception,
        )

        return result
