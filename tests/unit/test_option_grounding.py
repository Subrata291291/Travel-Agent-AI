import json
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.graph import GraphContext, TravelAgentGraph
from app.database.models import Tenant
from app.schemas.perception import TripPerception
from app.schemas.trip import TravelPlan, TravelTask


def _flight_option():
    return {
        "option_id": "FLIGHT-1",
        "mode": "flight",
        "provider": "Example Air",
        "origin": "Kolkata",
        "destination": "Goa",
        "departure_time": "2026-12-20T08:00:00",
        "arrival_time": "2026-12-20T11:00:00",
        "duration_minutes": 180,
        "price": 13000.0,
        "currency": "INR",
    }


def test_compiled_transport_search_renders_authoritative_option_not_llm_text():
    option = _flight_option()

    class Memory:
        def get_messages(self, session_id, tenant_id):
            return []

        def get_context(self, session_id, tenant_id, user_id):
            return {}

    class Perception:
        def understand(self, user_message, history):
            return TripPerception(
                intent="find_transport",
                destination="Goa",
                start_date="2026-12-20",
                end_date="2026-12-23",
                travellers=2,
                budget=30000.0,
                currency="INR",
            )

    class DestinationResolver:
        def resolve(self, destination):
            return {
                "status": "resolved",
                "location": {
                    "name": "Goa",
                    "latitude": 15.3,
                    "longitude": 74.0,
                    "country": "India",
                },
                "candidates": [],
            }

    class Planner:
        def create_plan(self, perception, memory_context):
            return TravelPlan(
                goal="Find transport to Goa.",
                tasks=[
                    TravelTask(
                        task_id="transport-1",
                        task_type="transport",
                        description="Search for transport options.",
                    )
                ],
            )

    class Router:
        def __init__(self):
            self.calls = 0

        def invoke_with_tools(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_flights",
                            "args": {
                                "origin": "Kolkata",
                                "destination": "Goa",
                                "departure_date": "2026-12-20",
                                "travellers": 2,
                            },
                            "id": "flight-search-1",
                            "type": "tool_call",
                        }
                    ],
                )
            # This deliberately contradicts the authoritative option result.
            return AIMessage(content="FLIGHT-1 costs 6500 INR.")

    class ToolExecutor:
        def execute(self, tool_call):
            return ToolMessage(
                content=json.dumps([option]),
                tool_call_id=tool_call["id"],
            )

    graph = TravelAgentGraph()
    router = Router()
    graph.memory = Memory()
    graph.perception_agent = Perception()
    graph.destination_resolver = DestinationResolver()
    graph.planner_agent = Planner()
    graph.router = router
    graph.tool_executor = ToolExecutor()

    result = graph.graph.invoke(
        {
            "user_message": "Find a flight from Kolkata to Goa.",
            "user_id": "user_demo",
            "tenant_id": "tenant_demo",
            "session_id": "option-grounding-001",
            "messages": [
                HumanMessage(content="Find a flight from Kolkata to Goa.")
            ],
            "perception": None,
            "plan": None,
            "destination_resolution": None,
            "clarification_needed": False,
            "pending_clarification": None,
            "pending_destination": None,
            "pending_destination_candidates": [],
            "tool_context": None,
            "trip_context": None,
            "transport_options": [],
            "hotel_options": [],
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

    assert router.calls == 1
    assert result["transport_options"] == [option]
    assert result["transport_options"][0]["price"] == 13000.0
    assert result["selected_option_id"] is None
    assert "Price: 13000.0 INR" in result["messages"][-1].content
    assert "6500" not in result["messages"][-1].content


def test_valid_transport_selection_confirms_using_canonical_option():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    option = _flight_option()
    result = graph.booking_confirmation_node(
        {
            "perception": TripPerception(
                intent="book_trip",
                selected_option_id="FLIGHT-1",
                travellers=2,
            ),
            "transport_options": [option],
        }
    )

    assert result["selected_option_id"] == "FLIGHT-1"
    assert result["pending_booking_confirmation"] is True
    assert "Price: 13000.0 INR" in result["messages"][0].content
    assert "6500" not in result["messages"][0].content


def test_unknown_transport_selection_is_rejected():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    result = graph.booking_confirmation_node(
        {
            "perception": TripPerception(
                intent="book_trip",
                selected_option_id="FLIGHT-99",
                travellers=2,
            ),
            "transport_options": [_flight_option()],
        }
    )

    assert result["pending_booking_confirmation"] is False
    assert "couldn't find transport option FLIGHT-99" in result["messages"][0].content


def test_confirmed_transport_booking_total_uses_authoritative_price(test_db):
    test_db.add(Tenant(tenant_id="tenant_demo", name="Demo", slug="demo"))
    test_db.commit()

    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    option = _flight_option()
    state = {
        "pending_booking_confirmation": True,
        "perception": TripPerception(
            intent="book_trip",
            selected_option_id="FLIGHT-1",
            confirmation="yes",
            travellers=2,
        ),
        "selected_option_id": "FLIGHT-1",
        "transport_options": [option],
        "user_id": "user_demo",
        "tenant_id": "tenant_demo",
        "session_id": "option-grounding-booking",
    }
    runtime = SimpleNamespace(context=GraphContext(db=test_db))

    result = graph.booking_execution_node(state, runtime)

    assert result["booking"]["price"] == 13000.0
    assert result["booking"]["travellers"] == 2
    assert result["booking"]["total_price"] == 26000.0
    assert result["booking"]["status"] == "confirmed"
    assert "Total: 26000.0 INR" in result["messages"][0].content


def test_hotel_recommendation_uses_authoritative_prices_and_details():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    result = graph.structured_options_node(
        {
            "transport_search_performed": False,
            "hotel_search_performed": True,
            "hotel_options": [
                {
                    "hotel_id": "HOTEL-3",
                    "name": "Mock Budget Stay",
                    "destination": "Goa",
                    "check_in_date": "2026-12-20",
                    "check_out_date": "2026-12-23",
                    "price_per_night": 2200.0,
                    "total_price": 6600.0,
                    "currency": "INR",
                    "rating": 4.0,
                    "amenities": ["WiFi"],
                }
            ],
        }
    )

    answer = result["messages"][0].content
    assert "Price per night: 2200.0 INR" in answer
    assert "Total stay price: 6600.0 INR" in answer
    assert "Check-in: 2026-12-20" in answer
    assert "Rating: 4.0/5" in answer
    assert "Amenities: WiFi" in answer
