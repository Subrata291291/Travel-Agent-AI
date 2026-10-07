from app.memory.short_term import ShortTermMemory


def main():

    memory = ShortTermMemory()

    session_id = "user_001"
    tenant_id = "tenant_demo"

    memory.add_message(
        session_id,
        tenant_id,
        "human",
        "I want to visit Manali."
    )

    memory.add_message(
        session_id,
        tenant_id,
        "assistant",
        "Sure! How many days?"
    )

    memory.add_message(
        session_id,
        tenant_id,
        "human",
        "4 days."
    )

    print("\n==============================")
    print("SHORT TERM MEMORY")
    print("==============================\n")

    messages = memory.get_messages(
        session_id,
        tenant_id,
    )

    for message in messages:
        print(
            f"{message['role']}: "
            f"{message['content']}"
        )


if __name__ == "__main__":
    main()
