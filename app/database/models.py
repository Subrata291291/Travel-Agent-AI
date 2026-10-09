from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
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

    tenant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tenants.tenant_id"),
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

    tenant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tenants.tenant_id"),
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

class WorkflowState(Base):
    """
    Durable representation of an agent workflow state.

    Role:
    - Stores an in-progress agent workflow.
    - Allows the agent to resume after a process restart.
    - Separates workflow persistence from conversation memory.
    - Makes the memory layer ready for PostgreSQL and multi-worker deployment.
    """

    __tablename__ = "workflow_states"

    # --------------------------------------------------------
    # Session identifier
    # --------------------------------------------------------

    session_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tenants.tenant_id"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # User ownership
    # --------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Serialized workflow state
    # --------------------------------------------------------
    #
    # The complete LangGraph state will be stored here.
    #
    # Example:
    #
    # {
    #     "pending_booking_confirmation": True,
    #     "pending_booking_domain": "hotel",
    #     "selected_option_id": "HOTEL-2",
    #     ...
    # }
    #
    # We use Text for now because SQLite does not need
    # a PostgreSQL-specific JSON type at this stage.
    #

    state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # --------------------------------------------------------
    # Timestamps
    # --------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

class Tenant(Base):
    """
    Represents one customer/account in the SaaS platform.

    A tenant may represent:
    - a travel company
    - a travel agency
    - an organization
    - or an individual SaaS account
    """

    __tablename__ = "tenants"

    # --------------------------------------------------------
    # Primary identifier
    # --------------------------------------------------------

    tenant_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    # --------------------------------------------------------
    # Tenant information
    # --------------------------------------------------------

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )

    # --------------------------------------------------------
    # Tenant status
    # --------------------------------------------------------

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
    )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

class User(Base):
    """
    Represents a user belonging to a tenant.

    The tenant_id field establishes the SaaS ownership boundary.
    """

    __tablename__ = "users"
    __table_args__ = (Index("uq_users_email_lower", text("lower(email)"), unique=True),)

    # --------------------------------------------------------
    # Primary identifier
    # --------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    # --------------------------------------------------------
    # Tenant ownership
    # --------------------------------------------------------

    tenant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tenants.tenant_id"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # User information
    # --------------------------------------------------------

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )

    profile_picture_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # --------------------------------------------------------
    # Authorization foundation
    # --------------------------------------------------------

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="user",
    )

    # --------------------------------------------------------
    # Account status
    # --------------------------------------------------------

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
    )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


    user_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tenants.tenant_id"),
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="user",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
