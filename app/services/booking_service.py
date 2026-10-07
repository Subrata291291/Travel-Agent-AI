from uuid import uuid4
import hashlib

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
    Business layer responsible for creating and managing bookings.

    Role:
    - Validate booking input.
    - Generate stable idempotency keys.
    - Prevent duplicate bookings.
    - Calculate total price.
    - Create the Booking database object.
    - Persist it through BookingRepository.
    - Retrieve bookings securely.
    - Cancel bookings according to business rules.
    - Return clean BookingResponse objects.

    Important:
    - The LLM does NOT directly control this service.
    - The application calls this service only after explicit
      booking confirmation.
    """

    def __init__(self):
        # Development-time database bootstrap.
        init_db()

    # ========================================================
    # INTERNAL HELPERS
    # ========================================================

    @staticmethod
    def _build_idempotency_key(
        request: BookingRequest,
        selected_option: dict,
    ) -> str:
        """
        Build a stable idempotency key for a booking.

        IMPORTANT:
        session_id is intentionally NOT included.

        Why?

        A user can start a new conversation/session and still
        attempt to book the exact same itinerary.

        The idempotency key therefore represents the actual
        booking intent rather than the chat session.

        Current identity:

        user
        + option
        + mode
        + origin
        + destination
        + departure
        + arrival
        + travellers
        """

        idempotency_source = "|".join(
            [
                str(request.tenant_id),
                str(request.user_id),
                str(request.option_id),
                str(selected_option.get("mode", "")),
                str(selected_option.get("origin", "")),
                str(selected_option.get("destination", "")),
                str(selected_option.get("departure_time", "")),
                str(selected_option.get("arrival_time", "")),
                str(request.travellers),
            ]
        )

        return hashlib.sha256(
            idempotency_source.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _build_legacy_idempotency_key(
        request: BookingRequest,
        selected_option: dict,
    ) -> str:
        """Return the pre-tenant key for safely finding existing rows."""
        legacy_source = "|".join(
            [
                str(request.user_id),
                str(request.option_id),
                str(selected_option.get("mode", "")),
                str(selected_option.get("origin", "")),
                str(selected_option.get("destination", "")),
                str(selected_option.get("departure_time", "")),
                str(selected_option.get("arrival_time", "")),
                str(request.travellers),
            ]
        )
        return hashlib.sha256(legacy_source.encode("utf-8")).hexdigest()

    @classmethod
    def _find_existing_booking(
        cls,
        repository: BookingRepository,
        request: BookingRequest,
        selected_option: dict,
    ) -> Booking | None:
        for idempotency_key in (
            cls._build_idempotency_key(request, selected_option),
            cls._build_legacy_idempotency_key(request, selected_option),
        ):
            booking = repository.get_booking_by_idempotency_key(
                idempotency_key=idempotency_key,
                tenant_id=request.tenant_id,
            )
            if booking:
                return booking
        return None

    @staticmethod
    def _to_response(
        booking: Booking,
    ) -> BookingResponse:
        """
        Convert a database Booking object into the stable
        application-level BookingResponse schema.
        """

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

    # ========================================================
    # CREATE BOOKING
    # ========================================================
    def get_existing_booking(
        self,
        request: BookingRequest,
        selected_option: dict,
    ) -> BookingResponse | None:
        """
        Check whether the exact booking intent has already
        been confirmed.

        This uses the same stable idempotency key as
        create_booking().

        Important:
        - session_id is NOT part of the idempotency identity.
        - Different chat sessions can therefore resolve to
        the same existing booking.
        """

        db = SessionLocal()

        try:
            repository = BookingRepository(db)

            booking = self._find_existing_booking(
                repository,
                request,
                selected_option,
            )

            if not booking:
                return None

            return self._to_response(
                booking
            )

        finally:
            db.close()

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
        # 2. Generate stable idempotency key
        # ----------------------------------------------------
        #
        # IMPORTANT:
        # session_id is intentionally NOT included.
        #
        # This allows duplicate protection to work even when
        # the same user starts a new chat session.
        # ----------------------------------------------------

        idempotency_key = self._build_idempotency_key(
            request=request,
            selected_option=selected_option,
        )

        # ----------------------------------------------------
        # 3. Database session
        # ----------------------------------------------------

        db = SessionLocal()

        try:
            repository = BookingRepository(db)

            # ------------------------------------------------
            # 4. Check existing booking by idempotency key
            # ------------------------------------------------
            #
            # This is the main duplicate protection.
            #
            # Same user + same itinerary across different
            # sessions will produce the same key.
            # ------------------------------------------------

            existing_booking = self._find_existing_booking(
                repository,
                request,
                selected_option,
            )

            if existing_booking:

                return self._to_response(
                    existing_booking
                )

            # ------------------------------------------------
            # 5. Calculate price
            # ------------------------------------------------

            price = float(
                selected_option.get("price", 0)
            )

            total_price = (
                price * request.travellers
            )

            # ------------------------------------------------
            # 6. Generate booking ID
            # ------------------------------------------------

            booking_id = (
                f"BOOK-{uuid4().hex[:12].upper()}"
            )

            # ------------------------------------------------
            # 7. Create database booking object
            # ------------------------------------------------

            booking = Booking(
                booking_id=booking_id,

                user_id=request.user_id,
                tenant_id=request.tenant_id,

                # Keep the current conversation/session ID
                # for audit/history purposes.
                session_id=request.session_id,

                option_id=request.option_id,

                # IMPORTANT:
                # Persist the stable idempotency key.
                idempotency_key=idempotency_key,

                mode=selected_option.get(
                    "mode",
                    "",
                ),

                provider=selected_option.get(
                    "provider",
                    "",
                ),

                origin=selected_option.get(
                    "origin",
                    "",
                ),

                destination=selected_option.get(
                    "destination",
                    "",
                ),

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

            # ------------------------------------------------
            # 8. Persist booking
            # ------------------------------------------------

            try:

                booking = repository.create(
                    booking
                )

            except IntegrityError:

                # ------------------------------------------------
                # Race-condition protection
                # ------------------------------------------------
                #
                # Example:
                #
                # Request A → checks key → nothing found
                # Request B → checks key → nothing found
                #
                # Both try INSERT at almost the same time.
                #
                # Database UNIQUE constraint allows only one.
                #
                # If this request loses the race, retrieve the
                # booking that was created by the other request.
                # ------------------------------------------------

                db.rollback()

                existing_booking = self._find_existing_booking(
                    repository,
                    request,
                    selected_option,
                )

                if not existing_booking:
                    raise

                booking = existing_booking

            # ------------------------------------------------
            # 9. Return stable application response
            # ------------------------------------------------

            return self._to_response(
                booking
            )

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

    # ========================================================
    # GET BOOKING BY ID
    # ========================================================

    def get_booking(
        self,
        booking_id: str,
        user_id: str,
        tenant_id: str,
    ) -> BookingResponse:
        """
        Retrieve one booking by its public booking ID.

        Business rules:
        - Booking must exist.
        - Booking must belong to the current user.
        - The LLM does not directly access the database.
        - The repository performs the database lookup.
        """

        db = SessionLocal()

        try:
            repository = BookingRepository(db)

            # ------------------------------------------------
            # 1. Find booking
            # ------------------------------------------------

            booking = repository.get_by_id(
                booking_id,
                user_id,
                tenant_id,
            )

            if not booking:
                raise ValueError(
                    f"Booking {booking_id} was not found."
                )

            # ------------------------------------------------
            # 3. Return stable application response
            # ------------------------------------------------

            return self._to_response(
                booking
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
        tenant_id: str,
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

            # ------------------------------------------------
            # 1. Find booking
            # ------------------------------------------------

            booking = repository.get_by_id(
                booking_id,
                user_id,
                tenant_id,
            )

            if not booking:
                raise ValueError(
                    f"Booking {booking_id} was not found."
                )

            # ------------------------------------------------
            # 3. Already cancelled?
            # ------------------------------------------------

            if booking.status == "cancelled":
                raise ValueError(
                    f"Booking {booking_id} is already cancelled."
                )

            # ------------------------------------------------
            # 4. Only confirmed bookings can be cancelled
            # ------------------------------------------------

            if booking.status != "confirmed":
                raise ValueError(
                    f"Booking {booking_id} cannot be cancelled "
                    f"because its current status is "
                    f"{booking.status}."
                )

            # ------------------------------------------------
            # 5. Change booking state
            # ------------------------------------------------

            booking.status = "cancelled"

            # ------------------------------------------------
            # 6. Persist transaction
            # ------------------------------------------------

            db.commit()
            db.refresh(booking)

            # ------------------------------------------------
            # 7. Return stable application response
            # ------------------------------------------------

            return self._to_response(
                booking
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
        tenant_id: str,
    ) -> list[BookingResponse]:

        db = SessionLocal()

        try:
            repository = BookingRepository(db)

            bookings = repository.get_user_bookings(
                user_id=user_id,
                tenant_id=tenant_id
            )

            return [
                self._to_response(
                    booking
                )
                for booking in bookings
            ]

        finally:
            db.close()
