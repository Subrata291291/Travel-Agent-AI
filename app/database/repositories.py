from sqlalchemy import select

from app.database.models import Booking, HotelBooking


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