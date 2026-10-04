from app.memory.preferences import PreferenceMemory


def main():

    memory = PreferenceMemory()

    user_id = "user_001"

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

    print("\n==============================")
    print("LONG TERM PREFERENCES")
    print("==============================\n")

    preferences = memory.get_preferences(
        user_id
    )

    for preference in preferences:
        print(f"- {preference}")


if __name__ == "__main__":
    main()