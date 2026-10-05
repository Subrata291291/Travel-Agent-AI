from app.agents.perception import PerceptionAgent
from app.llm.router import LLMRouter


def main():

    router = LLMRouter()
    perception = PerceptionAgent(router)

    # =========================================================
    # TEST 1: TRANSPORT SEARCH
    # =========================================================

    user_message = """
I want to travel from Kolkata to Manali on December 20, 2026
for 2 travellers. Show me flight, train, and bus options.
"""

    result = perception.understand(user_message)

    print("\n==============================")
    print("TEST 1: TRANSPORT SEARCH")
    print("==============================\n")

    print(result.model_dump_json(indent=2))


    # =========================================================
    # TEST 2: BOOKING SELECTION
    # =========================================================

    conversation_history = [
        {
            "role": "user",
            "content": (
                "I want to travel from Kolkata to Manali on "
                "December 20, 2026 for 2 travellers. "
                "Show me flight, train, and bus options."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "Available transport options:\n"
                "FLIGHT-1 - Flight - ₹13,000\n"
                "TRAIN-1 - Train - ₹4,200\n"
                "BUS-1 - Bus - ₹3,600"
            ),
        },
    ]

    booking_result = perception.understand(
        user_message="Book TRAIN-1",
        conversation_history=conversation_history,
    )

    print("\n==============================")
    print("TEST 2: BOOKING SELECTION")
    print("==============================\n")

    print(booking_result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()