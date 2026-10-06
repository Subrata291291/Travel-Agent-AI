from app.agents.perception import PerceptionAgent
from app.llm.router import LLMRouter


def main():
    router = LLMRouter()
    agent = PerceptionAgent(router)

    message = "Cancel BOOK-29F06E436FF9"

    result = agent.understand(
        user_message=message,
        conversation_history=[],
    )

    print("\n===== PERCEPTION RESULT =====")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()