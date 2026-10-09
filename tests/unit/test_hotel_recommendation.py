from langchain_core.messages import HumanMessage

from app.agents.graph import GraphContext, TravelAgentGraph
from app.agents.perception import PerceptionAgent
from app.schemas.perception import TripPerception


def _hotel_options():
    return [
        {
            "hotel_id": "HOTEL-1",
            "name": "Mock Mountain View Hotel",
            "destination": "Goa",
            "check_in_date": "2026-12-20",
            "check_out_date": "2026-12-23",
            "price_per_night": 3500.0,
            "currency": "INR",
            "rating": 4.3,
            "amenities": ["WiFi", "Breakfast", "Parking"],
        },
        {
            "hotel_id": "HOTEL-2",
            "name": "Mock Valley Resort",
            "destination": "Goa",
            "check_in_date": "2026-12-20",
            "check_out_date": "2026-12-23",
            "price_per_night": 5000.0,
            "total_price": 15000.0,
            "currency": "INR",
            "rating": 4.6,
            "amenities": ["WiFi", "Breakfast", "Mountain View", "Parking"],
        },
        {
            "hotel_id": "HOTEL-3",
            "name": "Mock Budget Stay",
            "destination": "Goa",
            "check_in_date": "2026-12-20",
            "check_out_date": "2026-12-23",
            "price_per_night": 2200.0,
            "currency": "INR",
            "rating": 4.0,
            "amenities": ["WiFi"],
        },
    ]


def test_hotel_recommendation_phrases_are_recognized_without_llm():
    perception = PerceptionAgent(llm_router=None)

    for message in (
        "Which hotel do you recommend?",
        "Which hotel is best?",
        "What hotel would you suggest?",
        "Recommend a hotel for me.",
        "What is the best hotel option?",
    ):
        result = perception.understand(message)
        assert result.intent == "recommend_hotel"
        assert result.selected_option_id is None


def test_contextual_which_one_request_is_hotel_recommendation():
    perception = PerceptionAgent(llm_router=None)
    result = perception.understand(
        "Which one should I choose?",
        [
            {
                "role": "assistant",
                "content": (
                    "Available hotel options:\nHotel ID: HOTEL-1\n"
                    "Hotel ID: HOTEL-2"
                ),
            }
        ],
    )

    assert result.intent == "recommend_hotel"


def test_live_graph_recommendation_uses_canonical_hotel_and_does_not_select_or_book():
    class Memory:
        def get_messages(self, session_id, tenant_id):
            return [
                {
                    "role": "assistant",
                    "content": "Available hotel options:\nHotel ID: HOTEL-1",
                }
            ]

    graph = TravelAgentGraph()
    graph.memory = Memory()
    graph.perception_agent = PerceptionAgent(llm_router=None)

    result = graph.graph.invoke(
        {
            "user_message": "Which hotel do you recommend?",
            "user_id": "user_demo",
            "tenant_id": "tenant_demo",
            "session_id": "hotel-recommendation-001",
            "messages": [
                HumanMessage(content="Which hotel do you recommend?")
            ],
            "perception": None,
            "plan": None,
            "destination_resolution": None,
            "clarification_needed": False,
            "pending_clarification": None,
            "pending_destination": None,
            "pending_destination_candidates": [],
            "tool_context": None,
            "trip_context": {
                "intent": "find_hotel",
                "destination": "Goa",
                "start_date": "2026-12-20",
                "end_date": "2026-12-23",
                "travellers": 2,
                "budget": 20000.0,
                "currency": "INR",
            },
            "transport_options": [],
            "hotel_options": _hotel_options(),
            "hotel_search_performed": False,
            "transport_search_performed": False,
            "selected_option_id": None,
            "pending_booking_confirmation": False,
            "pending_booking_domain": None,
            "pending_cancellation_booking_id": None,
            "booking": None,
            "answer": None,
        },
        context=GraphContext(db=None),
    )

    answer = result["messages"][-1].content
    assert result["perception"].intent == "recommend_hotel"
    assert "I recommend HOTEL-2, Mock Valley Resort" in answer
    assert "highest listed rating (4.6/5)" in answer
    assert "₹15000 for 3 nights" in answer
    assert "WiFi, Breakfast, Mountain View, Parking" in answer
    assert result["selected_option_id"] is None
    assert result["pending_booking_confirmation"] is False
    assert result["booking"] is None


def test_unknown_hotel_id_is_not_retained_as_selection():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    result = graph.hotel_booking_confirmation_node(
        {
            "perception": TripPerception(
                intent="book_trip",
                selected_option_id="HOTEL-99",
            ),
            "hotel_options": _hotel_options(),
        }
    )

    assert result["selected_option_id"] is None
    assert result["pending_booking_confirmation"] is False
    assert "couldn't find hotel option HOTEL-99" in result["messages"][0].content


def test_explicit_hotel_choice_still_enters_confirmation_for_known_id():
    perception = PerceptionAgent(llm_router=None).understand("I choose HOTEL-2")
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    result = graph.hotel_booking_confirmation_node(
        {
            "perception": perception,
            "hotel_options": _hotel_options(),
        }
    )

    assert perception.intent == "book_trip"
    assert result["selected_option_id"] == "HOTEL-2"
    assert result["pending_booking_confirmation"] is True
    assert "Price per night: 5000.0 INR" in result["messages"][0].content
    assert "create an internal booking record" in result["messages"][0].content
    assert "does not reserve a room with the supplier" in result["messages"][0].content


def test_hotel_retry_routes_saved_booking_without_response_tenant_field():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    state = {
        "perception": TripPerception(
            intent="book_trip",
            selected_option_id="HOTEL-2",
        ),
        "booking": {
            "booking_id": "BOOK-C67446E915AF",
            "user_id": "user_demo",
            "session_id": "budget-check-001",
            "hotel_id": "HOTEL-2",
            "status": "confirmed",
        },
        "user_id": "user_demo",
        "tenant_id": "tenant_demo",
        "session_id": "budget-check-001",
        "pending_booking_confirmation": False,
        "pending_booking_domain": None,
    }

    assert graph.perception_route(state) == "hotel_existing_booking"
