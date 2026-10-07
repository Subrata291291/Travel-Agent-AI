from sqlalchemy import select

from app.database.models import (
    Booking,
    HotelBooking,
    WorkflowState,
)


class BookingRepository:
    def __init__(self, db):
        self.db = db

    def create(self, booking: Booking) -> Booking:
        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def get_by_id(self, booking_id: str) -> Booking | None:
        return self.db.scalar(
            select(Booking).where(
                Booking.booking_id == booking_id
            )
        )

    def get_confirmed_booking(
        self,
        user_id: str,
        session_id: str,
        option_id: str,
    ) -> Booking | None:
        """
        Find an already-confirmed booking for the same
        user + session + transport option.

        This is the first database-level protection
        against accidental duplicate booking.
        """

        return self.db.scalar(
            select(Booking)
            .where(
                Booking.user_id == user_id,
                Booking.session_id == session_id,
                Booking.option_id == option_id,
                Booking.status == "confirmed",
            )
            .order_by(Booking.created_at.desc())
        )

    def get_booking_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> Booking | None:
        """
        Find an existing booking using its stable idempotency key.

        Why this exists:
        - Prevents duplicate bookings across different chat sessions.
        - Uses the database-level unique idempotency key.
        - Returns the existing booking instead of creating another one.
        """

        return self.db.scalar(
            select(Booking)
            .where(
                Booking.idempotency_key == idempotency_key,
            )
        )

    def get_user_bookings(
        self,
        user_id: str,
    ) -> list[Booking]:
        """
        Return all bookings belonging to a user.

        Latest bookings are returned first.
        """

        return list(
            self.db.scalars(
                select(Booking)
                .where(
                    Booking.user_id == user_id
                )
                .order_by(
                    Booking.created_at.desc()
                )
            )
        )


class HotelBookingRepository:
    """
    Database access layer for hotel bookings.

    Role:
    - Create hotel booking records.
    - Find hotel bookings by ID.
    - Find confirmed hotel bookings.
    - Retrieve bookings belonging to a user.

    Business rules should remain in HotelBookingService.
    """

    def __init__(self, db):
        self.db = db

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    def create(self, booking):
        """
        Persist a new hotel booking.
        """

        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)

        return booking

    # --------------------------------------------------------
    # Find by booking ID
    # --------------------------------------------------------

    def get_by_id(self, booking_id: str):
        """
        Retrieve a hotel booking using its public booking ID.
        """

        return (
            self.db.query(HotelBooking)
            .filter(
                HotelBooking.booking_id == booking_id
            )
            .first()
        )

    # --------------------------------------------------------
    # Find confirmed booking
    # --------------------------------------------------------

    def get_confirmed_booking(
        self,
        user_id: str,
        hotel_id: str,
    ):
        """
        Find an existing confirmed hotel booking
        for the same user and hotel.
        """

        return (
            self.db.query(HotelBooking)
            .filter(
                HotelBooking.user_id == user_id,
                HotelBooking.hotel_id == hotel_id,
                HotelBooking.status == "confirmed",
            )
            .first()
        )

    # --------------------------------------------------------
    # Find by idempotency key
    # --------------------------------------------------------

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ):
        """
        Retrieve a booking using its idempotency key.

        This prevents accidental duplicate bookings.
        """

        return (
            self.db.query(HotelBooking)
            .filter(
                HotelBooking.idempotency_key
                == idempotency_key
            )
            .first()
        )

    # --------------------------------------------------------
    # User bookings
    # --------------------------------------------------------

    def get_user_bookings(
        self,
        user_id: str,
    ):
        """
        Retrieve all hotel bookings belonging to a user.
        """

        return (
            self.db.query(HotelBooking)
            .filter(
                HotelBooking.user_id == user_id
            )
            .order_by(
                HotelBooking.created_at.desc()
            )
            .all()
        )


class WorkflowStateRepository:
    """
    Repository for durable agent workflow state.

    Role:
    - Saves workflow state to the database.
    - Retrieves workflow state by session.
    - Updates existing workflow state.
    - Deletes workflow state when a workflow is finished.
    """

    def __init__(self, db):
        self.db = db

    # ========================================================
    # Get workflow state
    # ========================================================

    def get_workflow_state(
        self,
        session_id: str,
    ):
        return self.db.scalar(
            select(WorkflowState)
            .where(
                WorkflowState.session_id == session_id
            )
        )

    # ========================================================
    # Save / update workflow state
    # ========================================================

    def save_workflow_state(
        self,
        session_id: str,
        user_id: str,
        state: str,
    ):
        workflow_state = self.get_workflow_state(
            session_id
        )

        if workflow_state:

            workflow_state.user_id = user_id
            workflow_state.state = state

        else:

            workflow_state = WorkflowState(
                session_id=session_id,
                user_id=user_id,
                state=state,
            )

            self.db.add(workflow_state)

        self.db.commit()
        self.db.refresh(workflow_state)

        return workflow_state

    # ========================================================
    # Delete workflow state
    # ========================================================

    def delete_workflow_state(
        self,
        session_id: str,
    ):

        workflow_state = self.get_workflow_state(
            session_id
        )

        if workflow_state:

            self.db.delete(
                workflow_state
            )

            self.db.commit()

        return workflow_state