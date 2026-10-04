from app.agents.perception import PerceptionAgent
from app.llm.router import LLMRouter


def main():

    router = LLMRouter()

    perception = PerceptionAgent(router)

    user_message = """
    আমি আর আমার wife December 20-এর দিকে Manali যেতে চাই
    4 দিনের জন্য। আমার wife vegetarian এবং আমি long bus
    journey নিতে পারি না। আমাদের budget প্রায় 30,000 টাকা।
    """

    result = perception.understand(user_message)

    print("\n==============================")
    print("PERCEPTION RESULT")
    print("==============================\n")

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()