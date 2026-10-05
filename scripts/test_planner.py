from app.agents.perception import PerceptionAgent
from app.agents.planner import PlannerAgent
from app.llm.router import LLMRouter


def main():

    router = LLMRouter()

    perception_agent = PerceptionAgent(router)
    planner_agent = PlannerAgent(router)

    user_message = """
    I want to travel from Kolkata to Manali on December 20, 2026
for 2 travellers. Show me flight, train, and bus options.
    """

    # Step 1: Understand the user
    perception = perception_agent.understand(
        user_message
    )

    print("\n==============================")
    print("PERCEPTION")
    print("==============================\n")

    print(
        perception.model_dump_json(indent=2)
    )

    # Step 2: Create execution plan
    plan = planner_agent.create_plan(
        perception
    )

    print("\n==============================")
    print("TRAVEL PLAN")
    print("==============================\n")

    print(
        plan.model_dump_json(indent=2)
    )


if __name__ == "__main__":
    main()