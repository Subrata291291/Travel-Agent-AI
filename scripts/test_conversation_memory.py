from app.memory.conversation import ConversationMemory


def main():

    memory = ConversationMemory()

    user_id = "user_001"
    session_id = "session_001"

    # Current conversation
    memory.add_message(
        session_id,
        "human",
        "I want to visit Manali."
    )

    memory.add_message(
        session_id,
        "assistant",
        "Sure! How many days?"
    )

    memory.add_message(
        session_id,
        "human",
        "4 days."
    )

    # Long-term preferences
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

    # Get combined context
    context = memory.get_context(
        session_id,
        user_id,
    )

    print("\n==============================")
    print("CONVERSATION MEMORY")
    print("==============================\n")

    print("Conversation History:")

    for message in context[
        "conversation_history"
    ]:
        print(
            f"{message['role']}: "
            f"{message['content']}"
        )

    print("\nUser Preferences:")

    for preference in context[
        "user_preferences"
    ]:
        print(f"- {preference}")


if __name__ == "__main__":
    main()