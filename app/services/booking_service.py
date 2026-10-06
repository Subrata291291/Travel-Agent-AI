from uuid import uuid4

from app.database.connection import (
    SessionLocal,
    init_db,
)

from app.database.models import Booking

from app.database.repositories import (
    BookingRepository,
)

from app.schemas.booking import (
    BookingRequest,
    BookingResponse,
)
from sqlalchemy.exc import IntegrityError

class BookingService:
    """
    Business layer responsible for creating bookings.

    Role:
    - Validate booking input.
    - Calculate total price.
    - Create the Booking database object.
    - Persist it through BookingRepository.
    - Return a clean BookingResponse.

    Important:
    The LLM does NOT directly control this service.
    The application calls it only after explicit confirmation.
    """

    def __init__(self):
        # Development-time database bootstrap.
        init_db()

    # ========================================================
    # CREATE BOOKING
    # ========================================================
    def create_booking(
        self,
        request: BookingRequest,
        selected_option: dict,
    ) -> BookingResponse:

        # ----------------------------------------------------
        # 1. Validate selected option
        # ----------------------------------------------------

        if selected_option.get("option_id") != request.option_id:
            raise ValueError(
                "Selected transport option does not match "
                "the booking request."
            )

        # ----------------------------------------------------
        # 2. DUPLICATE BOOKING PROTECTION
        # ----------------------------------------------------
        #
        # If the exact same user/session/option already has
        # a confirmed booking, DO NOT create another booking.
        #
        # Instead, return the existing booking.
        # ----------------------------------------------------

        db = SessionLocal()

        try:
            repository = BookingRepository(db)

            existing_booking = repository.get_confirmed_booking(
                user_id=request.user_id,
                session_id=request.session_id,
                option_id=request.option_id,
            )

            if existing_booking:

                return BookingResponse(
                    booking_id=existing_booking.booking_id,
                    user_id=existing_booking.user_id,
                    session_id=existing_booking.session_id,
                    option_id=existing_booking.option_id,
                    status=existing_booking.status,
                    mode=existing_booking.mode,
                    provider=existing_booking.provider,
                    origin=existing_booking.origin,
                    destination=existing_booking.destination,
                    departure_time=existing_booking.departure_time,
                    arrival_time=existing_booking.arrival_time,
                    duration_minutes=existing_booking.duration_minutes,
                    price=existing_booking.price,
                    currency=existing_booking.currency,
                    travellers=existing_booking.travellers,
                    total_price=existing_booking.total_price,
                    created_at=existing_booking.created_at,
                )

            # ------------------------------------------------
            # 3. Create NEW booking
            # ------------------------------------------------

            price = float(
                selected_option.get("price", 0)
            )

            total_price = (
                price * request.travellers
            )

            booking_id = (
                f"BOOK-{uuid4().hex[:12].upper()}"
            )

            booking = Booking(
                booking_id=booking_id,
                user_id=request.user_id,
                session_id=request.session_id,
                option_id=request.option_id,
                mode=selected_option.get("mode", ""),
                provider=selected_option.get("provider", ""),
                origin=selected_option.get("origin", ""),
                destination=selected_option.get("destination", ""),
                departure_time=selected_option.get(
                    "departure_time",
                    "",
                ),
                arrival_time=selected_option.get(
                    "arrival_time",
                    "",
                ),
                duration_minutes=int(
                    selected_option.get(
                        "duration_minutes",
                        0,
                    )
                ),
                price=price,
                currency=selected_option.get(
                    "currency",
                    "INR",
                ),
                travellers=request.travellers,
                total_price=total_price,
                status="confirmed",
            )

            try:
                booking = repository.create(
                    booking
                )

            except IntegrityError:

                db.rollback()

                existing_booking = repository.get_confirmed_booking(
                    user_id=request.user_id,
                    session_id=request.session_id,
                    option_id=request.option_id,
                )

                if not existing_booking:
                    raise

                booking = existing_booking

            return BookingResponse(
                booking_id=booking.booking_id,
                user_id=booking.user_id,
                session_id=booking.session_id,
                option_id=booking.option_id,
                status=booking.status,
                mode=booking.mode,
                provider=booking.provider,
                origin=booking.origin,
                destination=booking.destination,
                departure_time=booking.departure_time,
                arrival_time=booking.arrival_time,
                duration_minutes=booking.duration_minutes,
                price=booking.price,
                currency=booking.currency,
                travellers=booking.travellers,
                total_price=booking.total_price,
                created_at=booking.created_at,
            )

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

    # ========================================================
    # CANCEL BOOKING
    # ========================================================
    def cancel_booking(
        self,
        booking_id: str,
        user_id: str,
    ) -> BookingResponse:
        """
        Cancel an existing booking.

        Business rules:
        - Booking must exist.
        - Booking must belong to the current user.
        - Booking must currently be confirmed.
        - Cancellation is performed by the application,
        never by the LLM.
        """

        db = SessionLocal()

        try:
            repository = BookingRepository(db)

            # --------------------------------------------------
            # 1. Find booking
            # --------------------------------------------------

            booking = repository.get_by_id(
                booking_id
            )

            if not booking:
                raise ValueError(
                    f"Booking {booking_id} was not found."
                )

            # --------------------------------------------------
            # 2. Ownership check
            # --------------------------------------------------

            if booking.user_id != user_id:
                raise PermissionError(
                    "You are not allowed to cancel this booking."
                )

            # --------------------------------------------------
            # 3. Already cancelled?
            # --------------------------------------------------

            if booking.status == "cancelled":
                raise ValueError(
                    f"Booking {booking_id} is already cancelled."
                )

            # --------------------------------------------------
            # 4. Only confirmed bookings can be cancelled
            # --------------------------------------------------

            if booking.status != "confirmed":
                raise ValueError(
                    f"Booking {booking_id} cannot be cancelled "
                    f"because its current status is "
                    f"{booking.status}."
                )

            # --------------------------------------------------
            # 5. Change booking state
            # --------------------------------------------------

            booking.status = "cancelled"

            # --------------------------------------------------
            # 6. Persist transaction
            # --------------------------------------------------

            db.commit()
            db.refresh(booking)

            # --------------------------------------------------
            # 7. Return stable application response
            # --------------------------------------------------

            return BookingResponse(
                booking_id=booking.booking_id,
                user_id=booking.user_id,
                session_id=booking.session_id,
                option_id=booking.option_id,
                status=booking.status,
                mode=booking.mode,
                provider=booking.provider,
                origin=booking.origin,
                destination=booking.destination,
                departure_time=booking.departure_time,
                arrival_time=booking.arrival_time,
                duration_minutes=booking.duration_minutes,
                price=booking.price,
                currency=booking.currency,
                travellers=booking.travellers,
                total_price=booking.total_price,
                created_at=booking.created_at,
            )

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

    # ========================================================
    # GET USER BOOKINGS
    # ========================================================

    def get_user_bookings(
        self,
        user_id: str,
    ) -> list[BookingResponse]:

        db = SessionLocal()

        try:
            repository = BookingRepository(db)

            bookings = repository.get_user_bookings(
                user_id=user_id
            )

            return [
                BookingResponse(
                    booking_id=booking.booking_id,
                    user_id=booking.user_id,
                    session_id=booking.session_id,
                    option_id=booking.option_id,
                    status=booking.status,
                    mode=booking.mode,
                    provider=booking.provider,
                    origin=booking.origin,
                    destination=booking.destination,
                    departure_time=booking.departure_time,
                    arrival_time=booking.arrival_time,
                    duration_minutes=booking.duration_minutes,
                    price=booking.price,
                    currency=booking.currency,
                    travellers=booking.travellers,
                    total_price=booking.total_price,
                    created_at=booking.created_at,
                )
                for booking in bookings
            ]

        finally:
            db.close()