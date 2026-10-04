from app.memory.short_term import ShortTermMemory


def main():

    memory = ShortTermMemory()

    session_id = "user_001"

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

    print("\n==============================")
    print("SHORT TERM MEMORY")
    print("==============================\n")

    messages = memory.get_messages(
        session_id
    )

    for message in messages:
        print(
            f"{message['role']}: "
            f"{message['content']}"
        )


if __name__ == "__main__":
    main()