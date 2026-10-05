from app.agents.perception import PerceptionAgent
from app.llm.router import LLMRouter


def main():

    router = LLMRouter()

    perception = PerceptionAgent(router)

    user_message = """
I want to travel from Kolkata to Manali on December 20, 2026
for 2 travellers. Show me flight, train, and bus options.
"""

    result = perception.understand(user_message)

    print("\n==============================")
    print("PERCEPTION RESULT")
    print("==============================\n")

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()