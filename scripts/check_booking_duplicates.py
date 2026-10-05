from sqlalchemy import text

from app.database.connection import engine


def check_booking_state():
    print("=" * 60)
    print("BOOKING IDEMPOTENCY STATE")
    print("=" * 60)

    with engine.connect() as connection:

        # ----------------------------------------------------
        # 1. Check total bookings
        # ----------------------------------------------------

        result = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM bookings
                """
            )
        )

        total_bookings = result.scalar()

        print()
        print(f"Total bookings: {total_bookings}")

        # ----------------------------------------------------
        # 2. Check NULL idempotency keys
        # ----------------------------------------------------

        result = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM bookings
                WHERE idempotency_key IS NULL
                """
            )
        )

        null_keys = result.scalar()

        print(
            f"Bookings with NULL idempotency_key: {null_keys}"
        )

        # ----------------------------------------------------
        # 3. Show current booking data
        # ----------------------------------------------------

        result = connection.execute(
            text(
                """
                SELECT
                    booking_id,
                    user_id,
                    session_id,
                    option_id,
                    idempotency_key,
                    status
                FROM bookings
                ORDER BY created_at
                """
            )
        )

        rows = result.fetchall()

        print()
        print("-" * 60)
        print("CURRENT BOOKINGS")
        print("-" * 60)

        if not rows:
            print("No bookings found.")

        for row in rows:
            print(
                f"Booking ID       : {row.booking_id}"
            )
            print(
                f"User ID          : {row.user_id}"
            )
            print(
                f"Session ID       : {row.session_id}"
            )
            print(
                f"Option ID        : {row.option_id}"
            )
            print(
                f"Idempotency Key  : {row.idempotency_key}"
            )
            print(
                f"Status           : {row.status}"
            )
            print("-" * 60)


if __name__ == "__main__":
    check_booking_state()