import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.graph import TravelAgentGraph
from app.agents.graph import GraphContext
from app.schemas.perception import TripPerception
from app.schemas.trip import TravelPlan, TravelTask


def test_confirmed_transport_and_hotel_over_total_budget_is_constraint_conflict():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    booking = {
        "booking_id": "BOOK-02112B3D57D1",
        "option_id": "FLIGHT-1",
        "mode": "flight",
        "status": "confirmed",
        "total_price": 26000.0,
        "currency": "INR",
        "travellers": 2,
    }
    state = {
        "perception": TripPerception(
            intent="find_hotel",
            destination="Goa",
            start_date="2026-12-20",
            end_date="2026-12-23",
            duration_days=3,
            travellers=2,
            budget=30000.0,
            currency="INR",
        ),
        "plan": TravelPlan(
            goal="Find a hotel in Goa within the total trip budget.",
            needs_clarification=True,
            clarification_questions=[
                "Would you like to adjust your budget or consider a cheaper hotel?"
            ],
        ),
        "booking": booking,
        "hotel_options": [
            {
                "hotel_id": "HOTEL-3",
                "name": "Mock Budget Stay",
                "destination": "Goa",
                "check_in_date": "2026-12-20",
                "check_out_date": "2026-12-23",
                "price_per_night": 2200.0,
                "currency": "INR",
                "travellers": 2,
            }
        ],
        "pending_booking_confirmation": False,
    }

    result = graph.planner_clarification_node(state)

    assert result["pending_clarification"] == "budget_conflict"
    assert result["pending_clarification"] != "trip_details"
    assert result["clarification_needed"] is True
    assert state["pending_booking_confirmation"] is False
    assert "booking" not in result
    answer = result["messages"][0].content
    assert "FLIGHT-1 booking costs INR 26,000" in answer
    assert "Mock Budget Stay (HOTEL-3), costs INR 6,600" in answer
    assert "INR 32,600" in answer
    assert "INR 2,600 over" in answer
    assert "dates" not in answer.lower()
    assert "travellers" not in answer.lower()
    assert state["booking"] == booking


def test_compiled_graph_stops_after_hotel_search_before_recommendation_llm():
    hotels = [
        {
            "hotel_id": "HOTEL-1",
            "name": "Hotel One",
            "destination": "Goa",
            "check_in_date": "2026-12-20",
            "check_out_date": "2026-12-23",
            "price_per_night": 3500.0,
            "currency": "INR",
            "travellers": 2,
        },
        {
            "hotel_id": "HOTEL-2",
            "name": "Hotel Two",
            "destination": "Goa",
            "check_in_date": "2026-12-20",
            "check_out_date": "2026-12-23",
            "price_per_night": 5000.0,
            "currency": "INR",
            "travellers": 2,
        },
        {
            "hotel_id": "HOTEL-3",
            "name": "Mock Budget Stay",
            "destination": "Goa",
            "check_in_date": "2026-12-20",
            "check_out_date": "2026-12-23",
            "price_per_night": 2200.0,
            "currency": "INR",
            "travellers": 2,
        },
    ]
    booking = {
        "booking_id": "BOOK-02112B3D57D1",
        "option_id": "FLIGHT-1",
        "mode": "flight",
        "status": "confirmed",
        "total_price": 26000.0,
        "currency": "INR",
        "travellers": 2,
    }

    class Memory:
        def get_messages(self, session_id, tenant_id, user_id=None):
            return []

        def get_context(self, session_id, tenant_id, user_id):
            return {}

    class Perception:
        def understand(self, user_message, history):
            return TripPerception(
                intent="find_hotel",
                destination="Goa",
                start_date="2026-12-20",
                end_date="2026-12-23",
                duration_days=3,
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
                goal="Find a hotel in Goa.",
                needs_clarification=False,
                tasks=[
                    TravelTask(
                        task_id="hotel-1",
                        task_type="hotel",
                        description="Search hotels for the trip dates.",
                    )
                ],
            )

    class Router:
        def __init__(self):
            self.calls = 0

        def invoke_with_tools(self, messages, tools):
            self.calls += 1
            if self.calls > 1:
                return AIMessage(content="An LLM recommendation was generated.")
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_hotels",
                        "args": {
                            "destination": "Goa",
                            "check_in_date": "2026-12-20",
                            "check_out_date": "2026-12-23",
                            "travellers": 2,
                        },
                        "id": "hotel-search-1",
                        "type": "tool_call",
                    }
                ],
            )

    class ToolExecutor:
        def execute(self, tool_call):
            return ToolMessage(
                content=json.dumps(hotels),
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
            "user_message": "Find a hotel in Goa for my trip.",
            "user_id": "user_demo",
            "tenant_id": "tenant_demo",
            "session_id": "budget-gate-001",
            "messages": [
                HumanMessage(content="Find a hotel in Goa for my trip.")
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
            "selected_option_id": None,
            "pending_booking_confirmation": False,
            "pending_booking_domain": None,
            "pending_cancellation_booking_id": None,
            "booking": booking,
            "answer": None,
        },
        context=GraphContext(db=None),
    )

    assert result["hotel_search_performed"] is True
    assert [hotel["hotel_id"] for hotel in result["hotel_options"]] == [
        "HOTEL-1",
        "HOTEL-2",
        "HOTEL-3",
    ]
    assert result["clarification_needed"] is True
    assert result["pending_clarification"] == "budget_conflict"
    assert result["selected_option_id"] is None
    assert result["pending_booking_confirmation"] is False
    assert result["booking"] == booking
    assert router.calls == 1
    answer = result["messages"][-1].content
    assert "FLIGHT-1 booking costs INR 26,000" in answer
    assert "Mock Budget Stay (HOTEL-3), costs INR 6,600" in answer
    assert "INR 32,600" in answer
    assert "INR 2,600 over" in answer
