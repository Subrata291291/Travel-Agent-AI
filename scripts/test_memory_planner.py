from app.agents.perception import PerceptionAgent
from app.agents.planner import PlannerAgent
from app.llm.router import LLMRouter
from app.memory.conversation import ConversationMemory


def main():

    # -------------------------
    # Initialize components
    # -------------------------

    router = LLMRouter()

    perception_agent = PerceptionAgent(
        router
    )

    planner_agent = PlannerAgent(
        router
    )

    memory = ConversationMemory()

    # -------------------------
    # User identity
    # -------------------------

    user_id = "user_001"
    session_id = "session_001"

    # -------------------------
    # Existing long-term
    # preferences
    # -------------------------

    memory.add_preference(
        user_id,
        "vegetarian"
    )

    memory.add_preference(
        user_id,
        "no long bus journey"
    )

    memory.add_preference(
        user_id,
        "prefers budget hotels"
    )

    # -------------------------
    # Current user message
    # -------------------------

    user_message = """
    I want to plan a 4-day trip to Manali
    for two people with a budget of 30000 INR.
    """

    # Store current message
    memory.add_message(
        session_id,
        "human",
        user_message,
    )

    # -------------------------
    # Perception
    # -------------------------

    perception = perception_agent.understand(
        user_message
    )

    print("\n==============================")
    print("PERCEPTION")
    print("==============================\n")

    print(
        perception.model_dump_json(indent=2)
    )

    # -------------------------
    # Retrieve memory
    # -------------------------

    memory_context = memory.get_context(
        session_id,
        user_id,
    )

    print("\n==============================")
    print("MEMORY CONTEXT")
    print("==============================\n")

    print(memory_context)

    # -------------------------
    # Planner
    # -------------------------

    plan = planner_agent.create_plan(
        perception,
        memory_context,
    )

    print("\n==============================")
    print("MEMORY-AWARE TRAVEL PLAN")
    print("==============================\n")

    print(
        plan.model_dump_json(indent=2)
    )


if __name__ == "__main__":
    main()