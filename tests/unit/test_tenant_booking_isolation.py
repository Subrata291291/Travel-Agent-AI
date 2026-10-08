import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.database.models import Booking, HotelBooking, Tenant
from app.services.booking_service import BookingService
from app.services.hotel_booking_service import HotelBookingService
from app.schemas.booking import BookingRequest
from app.schemas.hotel_booking import HotelBookingRequest


@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    with session_factory() as db:
        db.add_all(
            [
                Tenant(tenant_id="tenant_a", name="Tenant A", slug="tenant-a"),
                Tenant(tenant_id="tenant_b", name="Tenant B", slug="tenant-b"),
            ]
        )
        db.commit()

    yield session_factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _transport_request(tenant_id: str) -> BookingRequest:
    return BookingRequest(
        user_id="same-user-id",
        tenant_id=tenant_id,
        session_id=f"session-{tenant_id}",
        option_id="TRAIN-1",
        travellers=1,
    )


def _transport_option() -> dict:
    return {
        "option_id": "TRAIN-1",
        "mode": "train",
        "provider": "Rail",
        "origin": "A",
        "destination": "B",
        "departure_time": "2030-01-01T10:00:00",
        "arrival_time": "2030-01-01T11:00:00",
        "duration_minutes": 60,
        "price": 100.0,
        "currency": "INR",
    }


def _hotel_request(tenant_id: str) -> HotelBookingRequest:
    return HotelBookingRequest(
        user_id="same-user-id",
        tenant_id=tenant_id,
        session_id=f"session-{tenant_id}",
        hotel_id="HOTEL-1",
        travellers=1,
    )


def _selected_hotel() -> dict:
    return {
        "hotel_id": "HOTEL-1",
        "name": "Example Hotel",
        "provider": "Stay",
        "destination": "B",
        "check_in_date": "2030-01-01",
        "check_out_date": "2030-01-03",
        "price_per_night": 100.0,
        "currency": "INR",
    }


def test_transport_booking_read_and_list_are_tenant_scoped(db_session_factory):
    with db_session_factory() as db:
        service = BookingService(db)
        option = _transport_option()
        tenant_a = service.create_booking(_transport_request("tenant_a"), option)
        tenant_b = service.create_booking(_transport_request("tenant_b"), option)

        assert tenant_a.booking_id != tenant_b.booking_id
        assert [
            booking.booking_id
            for booking in service.get_user_bookings("same-user-id", "tenant_a")
        ] == [tenant_a.booking_id]
        with pytest.raises(ValueError, match="not found"):
            service.get_booking(tenant_a.booking_id, "same-user-id", "tenant_b")


def test_transport_cancellation_from_other_tenant_does_not_change_status(
    db_session_factory,
):
    with db_session_factory() as db:
        service = BookingService(db)
        booking = service.create_booking(
            _transport_request("tenant_a"),
            _transport_option(),
        )

        with pytest.raises(ValueError, match="not found"):
            service.cancel_booking(booking.booking_id, "same-user-id", "tenant_b")

    with db_session_factory() as db:
        stored = db.scalar(
            select(Booking).where(Booking.booking_id == booking.booking_id)
        )
        assert stored.status == "confirmed"


def test_transport_idempotency_is_tenant_scoped(db_session_factory):
    with db_session_factory() as db:
        service = BookingService(db)
        option = _transport_option()
        tenant_a = service.create_booking(_transport_request("tenant_a"), option)
        tenant_b = service.create_booking(_transport_request("tenant_b"), option)
        repeated_tenant_a = service.create_booking(
            _transport_request("tenant_a").model_copy(
                update={"session_id": "another-session"}
            ),
            option,
        )

        assert tenant_b.booking_id != tenant_a.booking_id
        assert tenant_b.user_id == tenant_a.user_id
        assert repeated_tenant_a.booking_id == tenant_a.booking_id


def test_hotel_booking_read_and_list_are_tenant_scoped(db_session_factory):
    with db_session_factory() as db:
        service = HotelBookingService(db)
        hotel = _selected_hotel()
        tenant_a = service.create_booking(_hotel_request("tenant_a"), hotel)
        tenant_b = service.create_booking(_hotel_request("tenant_b"), hotel)

        assert tenant_a.booking_id != tenant_b.booking_id
        assert [
            booking.booking_id
            for booking in service.get_user_bookings("same-user-id", "tenant_a")
        ] == [tenant_a.booking_id]
        with pytest.raises(ValueError, match="not found"):
            service.get_booking(tenant_a.booking_id, "same-user-id", "tenant_b")


def test_hotel_cancellation_from_other_tenant_does_not_change_status(
    db_session_factory,
):
    with db_session_factory() as db:
        service = HotelBookingService(db)
        booking = service.create_booking(
            _hotel_request("tenant_a"),
            _selected_hotel(),
        )

        with pytest.raises(ValueError, match="not found"):
            service.cancel_booking(booking.booking_id, "same-user-id", "tenant_b")

    with db_session_factory() as db:
        stored = db.scalar(
            select(HotelBooking).where(
                HotelBooking.booking_id == booking.booking_id
            )
        )
        assert stored.status == "confirmed"


def test_hotel_idempotency_is_tenant_scoped(db_session_factory):
    with db_session_factory() as db:
        service = HotelBookingService(db)
        hotel = _selected_hotel()
        tenant_a = service.create_booking(_hotel_request("tenant_a"), hotel)
        tenant_b = service.create_booking(_hotel_request("tenant_b"), hotel)
        repeated_tenant_a = service.create_booking(
            _hotel_request("tenant_a").model_copy(
                update={"session_id": "another-session"}
            ),
            hotel,
        )

        assert tenant_b.booking_id != tenant_a.booking_id
        assert tenant_b.user_id == tenant_a.user_id
        assert repeated_tenant_a.booking_id == tenant_a.booking_id
