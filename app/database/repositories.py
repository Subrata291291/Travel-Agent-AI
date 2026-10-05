from sqlalchemy import select

from app.database.models import Booking


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