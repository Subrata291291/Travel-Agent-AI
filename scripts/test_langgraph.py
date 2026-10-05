from app.agents.graph import TravelAgentGraph


# ============================================================
# RESULT PRINTER
# ============================================================

def print_result(
    title: str,
    result: dict,
):
    """
    Print the important information returned by one agent turn.

    Role:
    - Makes each test turn easy to inspect.
    - Shows perception, planning, destination resolution,
      booking state, and final answer.
    """

    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

    # --------------------------------------------------------
    # Perception
    # --------------------------------------------------------

    print("\nPERCEPTION")
    print("-" * 30)

    perception = result.get("perception")

    if perception is not None:
        print(
            perception.model_dump_json(
                indent=2
            )
        )
    else:
        print("Perception was not executed.")

    # --------------------------------------------------------
    # Plan
    # --------------------------------------------------------

    print("\nPLAN")
    print("-" * 30)

    plan = result.get("plan")

    if plan is not None:
        print(
            plan.model_dump_json(
                indent=2
            )
        )
    else:
        print("Planner was not executed.")

    # --------------------------------------------------------
    # Destination resolution
    # --------------------------------------------------------

    print("\nDESTINATION RESOLUTION")
    print("-" * 30)

    print(
        result.get(
            "destination_resolution"
        )
    )

    # --------------------------------------------------------
    # Transport options
    # --------------------------------------------------------

    print("\nTRANSPORT OPTIONS")
    print("-" * 30)

    transport_options = result.get(
        "transport_options",
        []
    )

    if transport_options:
        for option in transport_options:
            print(option)
    else:
        print("No transport options stored.")

    # --------------------------------------------------------
    # Booking state
    # --------------------------------------------------------

    print("\nBOOKING STATE")
    print("-" * 30)

    print(
        "Selected option:",
        result.get("selected_option_id"),
    )

    print(
        "Pending confirmation:",
        result.get(
            "pending_booking_confirmation",
            False,
        ),
    )

    # --------------------------------------------------------
    # Final answer
    # --------------------------------------------------------

    print("\nANSWER")
    print("-" * 30)

    print(
        result.get(
            "answer",
            "",
        )
    )


# ============================================================
# MAIN TEST
# ============================================================

def main():
    """
    Run a complete multi-turn travel-agent test.

    Role:
    - Create ONE TravelAgentGraph instance.
    - Use ONE session_id across all turns.
    - Verify that workflow state survives between turns.

    Test flow:

        Turn 1
            User asks for transport.

        Turn 2
            User resolves "Manali" to Himachal Pradesh.

        Turn 3
            User selects TRAIN-1 for booking.

        Expected Turn 3 behavior:
            The agent should find TRAIN-1 from the
            previously stored transport options and
            ask for explicit booking confirmation.
    """

    # --------------------------------------------------------
    # Create ONE agent instance.
    #
    # This is important because the current ConversationMemory
    # stores workflow state in memory.
    # --------------------------------------------------------

    agent = TravelAgentGraph()

    # --------------------------------------------------------
    # Use the SAME user and session for every turn.
    #
    # The session_id is the key used by ConversationMemory
    # to store/retrieve workflow state.
    # --------------------------------------------------------

    user_id = "user_001"
    session_id = "session_001"

    # ========================================================
    # TURN 1
    # ========================================================

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
        "TURN 1 — SEARCH TRANSPORT",
        result_1,
    )

    # ========================================================
    # TURN 2
    # ========================================================

    result_2 = agent.run(
        user_message="Himachal Pradesh",
        user_id=user_id,
        session_id=session_id,
    )

    print_result(
        "TURN 2 — DESTINATION CLARIFICATION",
        result_2,
    )

    # ========================================================
    # TURN 3
    # ========================================================

    result_3 = agent.run(
        user_message="Book TRAIN-1",
        user_id=user_id,
        session_id=session_id,
    )

    print_result(
        "TURN 3 — BOOK TRAIN-1",
        result_3,
    )

    result_4 = agent.run(
        user_message="Yes, book it",
        user_id=user_id,
        session_id=session_id,
    )

    print_result(
        "TURN 4 — CONFIRM BOOKING",
        result_4,
    )

    result_5 = agent.run(
        user_message="Yes, book it",
        user_id=user_id,
        session_id=session_id,
    )

    print_result("TURN 5 — DUPLICATE CONFIRMATION TEST", result_5)


    # ========================================================
    # TURN 6 — GET MY BOOKINGS
    # ========================================================

    print("=" * 70)
    print("TURN 6 — GET MY BOOKINGS")
    print("=" * 70)

    result = agent.run(
        user_id="user_001",
        session_id="session_001",
        user_message="Show my bookings",
    )

    print()
    print("PERCEPTION")
    print("-" * 30)

    perception = result.get("perception")

    if perception:
        print(
            perception.model_dump_json(
                indent=2
            )
        )

    print()
    print("ANSWER")
    print("-" * 30)

    messages = result.get("messages", [])

    if messages:
        print(
            messages[-1].content
        )

# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()