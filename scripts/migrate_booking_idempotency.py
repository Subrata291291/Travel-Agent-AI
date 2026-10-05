"""
Migration: finalize booking idempotency data.

Rules:
- Preserve every existing booking.
- For the same user/session/option combination:
    - latest confirmed booking = canonical
    - older records = legacy
- Every booking gets a unique idempotency_key.
- Finally create a UNIQUE index.
"""

from sqlalchemy import text

from app.database.connection import engine


TABLE_NAME = "bookings"
COLUMN_NAME = "idempotency_key"
INDEX_NAME = "uq_bookings_idempotency_key"


def column_exists(connection, table_name, column_name):
    result = connection.execute(
        text(f"PRAGMA table_info({table_name})")
    )

    return any(
        row[1] == column_name
        for row in result.fetchall()
    )


def index_exists(connection, index_name):
    result = connection.execute(
        text(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
              AND name = :index_name
            """
        ),
        {"index_name": index_name},
    )

    return result.fetchone() is not None


def migrate():
    print("=" * 60)
    print("BOOKING IDEMPOTENCY MIGRATION")
    print("=" * 60)

    with engine.begin() as connection:

        # ----------------------------------------------------
        # 1. Ensure column exists
        # ----------------------------------------------------

        if not column_exists(
            connection,
            TABLE_NAME,
            COLUMN_NAME,
        ):
            print("Adding idempotency_key column...")

            connection.execute(
                text(
                    """
                    ALTER TABLE bookings
                    ADD COLUMN idempotency_key VARCHAR(255)
                    """
                )
            )

            print("✓ idempotency_key column added.")

        else:
            print(
                "✓ idempotency_key column already exists."
            )

        # ----------------------------------------------------
        # 2. Read all bookings
        #
        # IMPORTANT:
        # Newest booking is read first.
        # Therefore the first booking for a logical
        # user/session/option combination becomes canonical.
        # ----------------------------------------------------

        result = connection.execute(
            text(
                """
                SELECT
                    booking_id,
                    user_id,
                    session_id,
                    option_id,
                    status,
                    created_at
                FROM bookings
                ORDER BY created_at DESC
                """
            )
        )

        bookings = result.fetchall()

        print()
        print(f"Found {len(bookings)} booking(s).")

        seen_logical_bookings = set()

        # ----------------------------------------------------
        # 3. Assign unique idempotency keys
        # ----------------------------------------------------

        for booking in bookings:

            booking_id = booking.booking_id
            user_id = booking.user_id
            session_id = booking.session_id
            option_id = booking.option_id

            logical_key = (
                f"{user_id}:"
                f"{session_id}:"
                f"{option_id}"
            )

            # -----------------------------------------------
            # Latest record becomes canonical
            # -----------------------------------------------

            if logical_key not in seen_logical_bookings:

                idempotency_key = (
                    f"booking:{logical_key}"
                )

                seen_logical_bookings.add(
                    logical_key
                )

                print(
                    f"CANONICAL → {booking_id}"
                )
                print(
                    f"Key       → {idempotency_key}"
                )

            # -----------------------------------------------
            # Older duplicate becomes legacy
            # -----------------------------------------------

            else:

                idempotency_key = (
                    f"legacy:{booking_id}"
                )

                print(
                    f"LEGACY    → {booking_id}"
                )
                print(
                    f"Key       → {idempotency_key}"
                )

            connection.execute(
                text(
                    """
                    UPDATE bookings
                    SET idempotency_key = :key
                    WHERE booking_id = :booking_id
                    """
                ),
                {
                    "key": idempotency_key,
                    "booking_id": booking_id,
                },
            )

        # ----------------------------------------------------
        # 4. Create UNIQUE index
        # ----------------------------------------------------

        if not index_exists(
            connection,
            INDEX_NAME,
        ):
            print()
            print(
                "Creating UNIQUE idempotency index..."
            )

            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX
                    uq_bookings_idempotency_key
                    ON bookings(idempotency_key)
                    """
                )
            )

            print(
                "✓ UNIQUE index created."
            )

        else:
            print(
                "✓ UNIQUE idempotency index already exists."
            )

    print()
    print("=" * 60)
    print("MIGRATION COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    migrate()