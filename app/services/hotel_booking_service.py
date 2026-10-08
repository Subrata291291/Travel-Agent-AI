from datetime import datetime
import hashlib
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import HotelBooking
from app.database.repositories import HotelBookingRepository
from app.schemas.hotel_booking import (
    HotelBookingRequest,
    HotelBookingResponse,
)


class HotelBookingService:
    """
    Business layer for hotel bookings.

    Responsibilities:
    - Validate the selected hotel.
    - Calculate number of nights.
    - Calculate total price.
    - Prevent duplicate bookings.
    - Create the durable hotel booking record.
    - Convert database records into API/application responses.

    The LLM must never directly create a HotelBooking.

    Database sessions are injected by the application layer.
    The service does not create or close database sessions itself.
    """

    def __init__(self, db: Session):
        """
        Receive the database session from the application layer.

        This keeps database ownership outside the business layer
        and allows tests to inject an isolated database.
        """

        self.db = db

    # --------------------------------------------------------
    # Helper: find existing booking
    # --------------------------------------------------------

    @staticmethod
    def _find_existing_booking(
        repository: HotelBookingRepository,
        idempotency_keys: tuple[str, str],
        tenant_id: str,
        user_id: str,
        session_id: str,
    ) -> HotelBooking | None:
        """
        Find an existing hotel booking using one of the
        supported idempotency keys.
        """

        for idempotency_key in idempotency_keys:
            booking = repository.get_by_idempotency_key(
                idempotency_key,
                tenant_id,
                user_id,
                session_id,
            )

            if booking:
                return booking

        return None

    # --------------------------------------------------------
    # Helper: calculate nights
    # --------------------------------------------------------

    def _calculate_nights(
        self,
        check_in_date: str,
        check_out_date: str,
    ) -> int:
        """
        Calculate the number of nights between check-in
        and check-out dates.

        Example:

            2026-12-20 → 2026-12-22
            = 2 nights
        """

        try:
            check_in = datetime.strptime(
                check_in_date,
                "%Y-%m-%d",
            ).date()

            check_out = datetime.strptime(
                check_out_date,
                "%Y-%m-%d",
            ).date()

        except ValueError as exc:
            raise ValueError(
                "Hotel dates must use YYYY-MM-DD format."
            ) from exc

        nights = (check_out - check_in).days

        if nights <= 0:
            raise ValueError(
                "Check-out date must be after check-in date."
            )

        return nights

    # --------------------------------------------------------
    # Helper: convert DB model → response
    # --------------------------------------------------------

    def _to_response(
        self,
        booking: HotelBooking,
    ) -> HotelBookingResponse:
        """
        Convert a database HotelBooking into the
        application-level HotelBookingResponse.
        """

        return HotelBookingResponse(
            booking_id=booking.booking_id,
            user_id=booking.user_id,
            session_id=booking.session_id,
            hotel_id=booking.hotel_id,
            hotel_name=booking.hotel_name,
            provider=booking.provider,
            destination=booking.destination,
            check_in_date=booking.check_in_date,
            check_out_date=booking.check_out_date,
            price_per_night=booking.price_per_night,
            currency=booking.currency,
            travellers=booking.travellers,
            nights=booking.nights,
            total_price=booking.total_price,
            status=booking.status,
            created_at=booking.created_at,
        )

    # --------------------------------------------------------
    # Create hotel booking
    # --------------------------------------------------------

    def create_booking(
        self,
        request: HotelBookingRequest,
        selected_hotel: dict,
    ) -> HotelBookingResponse:
        """
        Create a confirmed hotel booking.

        `selected_hotel` must come from the application's
        trusted hotel search results.

        The LLM is not trusted to provide pricing or
        hotel metadata.
        """

        # ----------------------------------------------------
        # 1. Validate selected hotel
        # ----------------------------------------------------

        hotel_id = selected_hotel.get("hotel_id")

        if not hotel_id:
            raise ValueError(
                "Selected hotel does not contain a hotel_id."
            )

        if hotel_id != request.hotel_id:
            raise ValueError(
                "Selected hotel does not match the booking request."
            )

        # ----------------------------------------------------
        # 2. Extract trusted hotel data
        # ----------------------------------------------------

        hotel_name = selected_hotel.get("name")
        provider = selected_hotel.get("provider")
        destination = selected_hotel.get("destination")
        check_in_date = selected_hotel.get("check_in_date")
        check_out_date = selected_hotel.get("check_out_date")
        price_per_night = selected_hotel.get("price_per_night")
        currency = selected_hotel.get("currency", "INR")

        required_fields = {
            "name": hotel_name,
            "provider": provider,
            "destination": destination,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "price_per_night": price_per_night,
        }

        missing_fields = [
            field
            for field, value in required_fields.items()
            if value is None
        ]

        if missing_fields:
            raise ValueError(
                "Selected hotel is missing required fields: "
                + ", ".join(missing_fields)
            )

        # ----------------------------------------------------
        # 3. Calculate number of nights
        # ----------------------------------------------------

        nights = self._calculate_nights(
            check_in_date,
            check_out_date,
        )

        # ----------------------------------------------------
        # 4. Calculate total price
        # ----------------------------------------------------

        total_price = price_per_night * nights

        # ----------------------------------------------------
        # 5. Create session-scoped idempotency key
        # ----------------------------------------------------

        # Retries of the same operation in one session reuse its key.
        # A new session represents a new booking operation.

        idempotency_source = "|".join(
            [
                str(request.tenant_id),
                str(request.user_id),
                str(request.session_id),
                str(request.hotel_id),
                str(check_in_date),
                str(check_out_date),
                str(request.travellers),
            ]
        )

        idempotency_key = hashlib.sha256(
            idempotency_source.encode("utf-8")
        ).hexdigest()

        # ----------------------------------------------------
        # Legacy idempotency key
        # ----------------------------------------------------

        legacy_idempotency_source = "|".join(
            [
                str(request.user_id),
                str(request.hotel_id),
                str(check_in_date),
                str(check_out_date),
                str(request.travellers),
            ]
        )

        legacy_idempotency_key = hashlib.sha256(
            legacy_idempotency_source.encode("utf-8")
        ).hexdigest()

        # ----------------------------------------------------
        # 6. Database transaction
        # ----------------------------------------------------

        db = self.db

        try:
            repository = HotelBookingRepository(db)

            # ------------------------------------------------
            # Check whether this exact booking already exists
            # ------------------------------------------------

            existing = self._find_existing_booking(
                repository,
                (
                    idempotency_key,
                    legacy_idempotency_key,
                ),
                request.tenant_id,
                request.user_id,
                request.session_id,
            )

            if existing:
                return self._to_response(existing)

            # ------------------------------------------------
            # Create booking
            # ------------------------------------------------

            booking = HotelBooking(
                booking_id=f"BOOK-{uuid4().hex[:12].upper()}",
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                session_id=request.session_id,
                hotel_id=request.hotel_id,
                hotel_name=hotel_name,
                provider=provider,
                destination=destination,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                idempotency_key=idempotency_key,
                price_per_night=price_per_night,
                currency=currency,
                travellers=request.travellers,
                nights=nights,
                total_price=total_price,
                status="confirmed",
            )

            try:
                booking = repository.create(booking)

            except IntegrityError:
                # Another request may have created the same
                # booking between our check and insert.

                db.rollback()

                existing = self._find_existing_booking(
                    repository,
                    (
                        idempotency_key,
                        legacy_idempotency_key,
                    ),
                    request.tenant_id,
                    request.user_id,
                    request.session_id,
                )

                if existing:
                    return self._to_response(existing)

                raise

            return self._to_response(booking)

        except Exception:
            db.rollback()
            raise

    # --------------------------------------------------------
    # Get booking
    # --------------------------------------------------------

    def get_booking(
        self,
        booking_id: str,
        user_id: str,
        tenant_id: str,
    ) -> HotelBookingResponse:
        """
        Retrieve one hotel booking securely.

        Business rules:
        - Booking must exist.
        - Booking must belong to current user.
        - Booking must belong to current tenant.
        """

        db = self.db

        repository = HotelBookingRepository(db)

        booking = repository.get_by_id(
            booking_id,
            user_id,
            tenant_id,
        )

        if not booking:
            raise ValueError(
                f"Hotel booking {booking_id} was not found."
            )

        return self._to_response(booking)

    # --------------------------------------------------------
    # Get user bookings
    # --------------------------------------------------------

    def get_user_bookings(
        self,
        user_id: str,
        tenant_id: str,
    ) -> list[HotelBookingResponse]:
        """
        Retrieve all hotel bookings belonging to a user
        inside the current tenant.
        """

        db = self.db

        repository = HotelBookingRepository(db)

        bookings = repository.get_user_bookings(
            user_id,
            tenant_id,
        )

        return [
            self._to_response(booking)
            for booking in bookings
        ]

    # --------------------------------------------------------
    # Cancel booking
    # --------------------------------------------------------

    def cancel_booking(
        self,
        booking_id: str,
        user_id: str,
        tenant_id: str,
    ) -> HotelBookingResponse:
        """
        Cancel an existing hotel booking.

        Business rules:
        - Booking must exist.
        - Booking must belong to current user.
        - Booking must belong to current tenant.
        - Booking must currently be confirmed.
        - Already cancelled booking cannot be cancelled again.
        - Cancellation is performed by the application,
          never by the LLM.
        """

        db = self.db

        try:
            repository = HotelBookingRepository(db)

            booking = repository.get_by_id(
                booking_id,
                user_id,
                tenant_id,
            )

            # ------------------------------------------------
            # 1. Booking must exist
            # ------------------------------------------------

            if not booking:
                raise ValueError(
                    f"Hotel booking {booking_id} was not found."
                )

            # ------------------------------------------------
            # 2. Already cancelled
            # ------------------------------------------------

            if booking.status == "cancelled":
                raise ValueError(
                    f"Hotel booking {booking_id} "
                    "is already cancelled."
                )

            # ------------------------------------------------
            # 3. Only confirmed bookings can be cancelled
            # ------------------------------------------------

            if booking.status != "confirmed":
                raise ValueError(
                    f"Hotel booking {booking_id} cannot be "
                    f"cancelled because its current status is "
                    f"{booking.status}."
                )

            # ------------------------------------------------
            # 4. Update status
            # ------------------------------------------------

            booking.status = "cancelled"

            # ------------------------------------------------
            # 5. Persist
            # ------------------------------------------------

            db.commit()
            db.refresh(booking)

            # ------------------------------------------------
            # 6. Return stable response
            # ------------------------------------------------

            return self._to_response(booking)

        except Exception:
            db.rollback()
            raise
