from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.connection import Base


class Booking(Base):
    """
    Database representation of a confirmed booking.

    Role:
    - Stores the durable booking record.
    - Separates booking persistence from conversation memory.
    - Allows us to retrieve bookings even after the conversation ends.
    """

    __tablename__ = "bookings"

    # --------------------------------------------------------
    # Primary identifier
    # --------------------------------------------------------

    booking_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    # --------------------------------------------------------
    # Ownership / session information
    # --------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    session_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Selected transport option
    # --------------------------------------------------------

    option_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Idempotency
    # --------------------------------------------------------

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # --------------------------------------------------------
    # Route
    # --------------------------------------------------------

    origin: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    destination: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # --------------------------------------------------------
    # Schedule
    # --------------------------------------------------------

    departure_time: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    arrival_time: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # --------------------------------------------------------
    # Pricing
    # --------------------------------------------------------

    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    travellers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # --------------------------------------------------------
    # Booking status
    # --------------------------------------------------------

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="confirmed",
    )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

class HotelBooking(Base):
    """
    Database representation of a confirmed hotel booking.

    Role:
    - Stores the durable hotel reservation.
    - Keeps hotel booking data separate from transport bookings.
    - Allows hotel bookings to be retrieved after the conversation ends.
    """

    __tablename__ = "hotel_bookings"

    # --------------------------------------------------------
    # Primary identifier
    # --------------------------------------------------------

    booking_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    # --------------------------------------------------------
    # Ownership / session information
    # --------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    session_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Selected hotel
    # --------------------------------------------------------

    hotel_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    hotel_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    destination: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # --------------------------------------------------------
    # Stay dates
    # --------------------------------------------------------

    check_in_date: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    check_out_date: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    # --------------------------------------------------------
    # Idempotency
    # --------------------------------------------------------

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # --------------------------------------------------------
    # Pricing
    # --------------------------------------------------------

    price_per_night: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    travellers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    nights: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # --------------------------------------------------------
    # Booking status
    # --------------------------------------------------------

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="confirmed",
    )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )