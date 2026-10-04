from app.llm.router import LLMRouter


def main():

    router = LLMRouter()

    messages = [
        (
            "system",
            "You are a helpful travel assistant."
        ),
        (
            "human",
            "Say hello to a user who wants to plan "
            "a 5-day trip to Goa."
        ),
    ]

    response = router.invoke(messages)

    print("\n==============================")
    print("Travel Agent LLM Response")
    print("==============================\n")

    print(response.content)


if __name__ == "__main__":
    main()