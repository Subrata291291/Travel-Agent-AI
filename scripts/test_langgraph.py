from app.agents.graph import TravelAgentGraph


def print_result(
    title: str,
    result: dict,
):

    print("\n==============================")
    print(title)
    print("==============================\n")

    print("PERCEPTION")
    print("------------------------------")

    print(
        result["perception"]
        .model_dump_json(indent=2)
    )

    print("\nPLAN")
    print("------------------------------")

    if result["plan"] is not None:
        print(
            result["plan"]
            .model_dump_json(indent=2)
        )
    else:
        print("Planner was not executed.")

    print("\nDESTINATION RESOLUTION")
    print("------------------------------")

    print(
        result["destination_resolution"]
    )

    print("\nANSWER")
    print("------------------------------")

    print(
        result["answer"]
    )


def main():

    agent = TravelAgentGraph()

    user_id = "user_001"
    session_id = "session_001"

    # ==========================================
    # TURN 1
    # ==========================================

    result_1 = agent.run(
        user_message=(
            "I want to travel from Kolkata to Manali on "
            "December 20, 2026 for 2 travellers. "
            "Show me flight, train, and bus options."
        ),
        user_id=user_id,
        session_id=session_id,
    )

    print_result(
        "TURN 1",
        result_1,
    )

    # ==========================================
    # TURN 2
    # ==========================================

    result_2 = agent.run(
        user_message=(
            "Himachal Pradesh"
        ),
        user_id=user_id,
        session_id=session_id,
    )

    print_result(
        "TURN 2",
        result_2,
    )


if __name__ == "__main__":
    main()