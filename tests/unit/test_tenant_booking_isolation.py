import pytest
import hashlib
from langchain_core.messages import HumanMessage
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.database.models import Booking, HotelBooking, Tenant
from app.services.booking_service import BookingService
from app.services.hotel_booking_service import HotelBookingService
from app.services.booking_query_service import BookingQueryService
from app.schemas.booking import BookingRequest
from app.schemas.hotel_booking import HotelBookingRequest
from app.agents.graph import GraphContext, TravelAgentGraph
from app.schemas.perception import TripPerception


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
        assert repeated_tenant_a.booking_id != tenant_a.booking_id


def test_hotel_retry_in_same_session_is_idempotent(db_session_factory):
    with db_session_factory() as db:
        service = HotelBookingService(db)
        request = _hotel_request("tenant_a")
        hotel = _selected_hotel()

        first = service.create_booking(request, hotel)
        retry = service.create_booking(request, hotel)

        assert retry.booking_id == first.booking_id
        assert retry.status == first.status == "confirmed"
        assert retry.total_price == 200.0


def test_new_session_does_not_reuse_cancelled_legacy_hotel_booking(
    db_session_factory,
):
    import hashlib

    from app.database.models import HotelBooking

    with db_session_factory() as db:
        old_request = _hotel_request("tenant_a").model_copy(
            update={"session_id": "smoke-test-hotel-001"}
        )
        hotel = _selected_hotel()
        legacy_source = "|".join(
            [
                old_request.user_id,
                old_request.hotel_id,
                hotel["check_in_date"],
                hotel["check_out_date"],
                str(old_request.travellers),
            ]
        )
        legacy_key = hashlib.sha256(
            legacy_source.encode("utf-8")
        ).hexdigest()
        old_booking = HotelBooking(
            booking_id="BOOK-EE3409258769",
            user_id=old_request.user_id,
            tenant_id=old_request.tenant_id,
            session_id=old_request.session_id,
            hotel_id=hotel["hotel_id"],
            hotel_name=hotel["name"],
            provider=hotel["provider"],
            destination=hotel["destination"],
            check_in_date=hotel["check_in_date"],
            check_out_date=hotel["check_out_date"],
            idempotency_key=legacy_key,
            price_per_night=100.0,
            currency="INR",
            travellers=1,
            nights=2,
            total_price=200.0,
            status="cancelled",
        )
        db.add(old_booking)
        db.commit()

        new_request = old_request.model_copy(
            update={"session_id": "hotel-booking-live-001"}
        )
        new_booking = HotelBookingService(db).create_booking(
            new_request,
            hotel,
        )
        old_after = db.get(HotelBooking, old_booking.booking_id)

        assert new_booking.booking_id != old_booking.booking_id
        assert new_booking.session_id == "hotel-booking-live-001"
        assert new_booking.status == "confirmed"
        assert old_after.status == "cancelled"


def test_same_hotel_intent_in_another_tenant_gets_separate_key(db_session_factory):
    with db_session_factory() as db:
        service = HotelBookingService(db)
        hotel = _selected_hotel()
        request_a = _hotel_request("tenant_a").model_copy(
            update={"session_id": "same-session"}
        )
        request_b = _hotel_request("tenant_b").model_copy(
            update={"session_id": "same-session"}
        )

        booking_a = service.create_booking(request_a, hotel)
        booking_b = service.create_booking(request_b, hotel)
        stored_a = db.get(HotelBooking, booking_a.booking_id)
        stored_b = db.get(HotelBooking, booking_b.booking_id)

        assert booking_a.booking_id != booking_b.booking_id
        assert stored_a.tenant_id == "tenant_a"
        assert stored_b.tenant_id == "tenant_b"


def test_compiled_hotel_confirmation_creates_new_booking_and_reports_db_status(
    test_db,
):
    from app.database.models import Tenant

    test_db.add(Tenant(tenant_id="tenant_demo", name="Demo", slug="demo"))
    hotel = {
        "hotel_id": "HOTEL-2",
        "name": "Mock Valley Resort",
        "provider": "Mock Hotel Provider",
        "destination": "Goa",
        "check_in_date": "2026-12-20",
        "check_out_date": "2026-12-23",
        "price_per_night": 5000.0,
        "currency": "INR",
        "travellers": 2,
    }
    legacy_source = "|".join(
        [
            "user_demo",
            "HOTEL-2",
            "2026-12-20",
            "2026-12-23",
            "2",
        ]
    )
    old_booking = HotelBooking(
        booking_id="BOOK-EE3409258769",
        user_id="user_demo",
        tenant_id="tenant_demo",
        session_id="smoke-test-hotel-001",
        hotel_id="HOTEL-2",
        hotel_name="Mock Valley Resort",
        provider="Mock Hotel Provider",
        destination="Goa",
        check_in_date="2026-12-20",
        check_out_date="2026-12-23",
        idempotency_key=hashlib.sha256(
            legacy_source.encode("utf-8")
        ).hexdigest(),
        price_per_night=5000.0,
        currency="INR",
        travellers=2,
        nights=3,
        total_price=15000.0,
        status="cancelled",
    )
    test_db.add(old_booking)
    test_db.commit()

    class Memory:
        def get_messages(self, session_id, tenant_id):
            return []

    class Perception:
        def understand(self, message, history):
            return TripPerception(
                intent="book_trip",
                destination="Goa",
                start_date="2026-12-20",
                end_date="2026-12-23",
                duration_days=3,
                travellers=2,
                budget=20000.0,
                currency="INR",
                selected_option_id="HOTEL-2",
                confirmation="yes",
            )

    graph = TravelAgentGraph()
    graph.memory = Memory()
    graph.perception_agent = Perception()
    result = graph.graph.invoke(
        {
            "user_message": "Yes, book this hotel.",
            "user_id": "user_demo",
            "tenant_id": "tenant_demo",
            "session_id": "hotel-booking-live-001",
            "messages": [HumanMessage(content="Yes, book this hotel.")],
            "perception": None,
            "plan": None,
            "destination_resolution": None,
            "clarification_needed": False,
            "pending_clarification": None,
            "pending_destination": None,
            "pending_destination_candidates": [],
            "tool_context": None,
            "trip_context": {
                "intent": "find_hotel",
                "destination": "Goa",
                "start_date": "2026-12-20",
                "end_date": "2026-12-23",
                "duration_days": 3,
                "travellers": 2,
                "budget": 20000.0,
                "currency": "INR",
            },
            "transport_options": [],
            "hotel_options": [hotel],
            "hotel_search_performed": False,
            "transport_search_performed": False,
            "selected_option_id": "HOTEL-2",
            "pending_booking_confirmation": True,
            "pending_booking_domain": "hotel",
            "pending_cancellation_booking_id": None,
            "booking": None,
            "answer": None,
        },
        context=GraphContext(db=test_db),
    )

    created = result["booking"]
    old_after = test_db.get(HotelBooking, old_booking.booking_id)
    stored = test_db.get(HotelBooking, created["booking_id"])
    answer = result["messages"][-1].content

    assert created["booking_id"] != old_booking.booking_id
    assert created["session_id"] == "hotel-booking-live-001"
    assert created["hotel_id"] == "HOTEL-2"
    assert created["nights"] == 3
    assert created["price_per_night"] == 5000.0
    assert created["total_price"] == 15000.0
    assert created["status"] == stored.status == "confirmed"
    assert old_after.status == "cancelled"
    assert "Hotel booking confirmed successfully!" in answer
    assert f"Status: {stored.status}" in answer
    assert result["pending_booking_confirmation"] is False

    retry = graph.graph.invoke(
        {
            **result,
            "user_message": "Yes, book this hotel.",
            "messages": [HumanMessage(content="Yes, book this hotel.")],
        },
        context=GraphContext(db=test_db),
    )
    retry_answer = retry["messages"][-1].content
    assert retry["booking"]["booking_id"] == created["booking_id"]
    assert retry["booking"]["status"] == "confirmed"
    assert retry["pending_booking_confirmation"] is False
    assert retry["selected_option_id"] is None
    assert "already confirmed" in retry_answer.lower()
    assert "Do you want me to book this hotel?" not in retry_answer
    assert test_db.query(HotelBooking).filter_by(
        session_id="hotel-booking-live-001"
    ).count() == 1

    cancelled_retry = graph.graph.invoke(
        {
            **result,
            "user_id": "user_demo",
            "tenant_id": "tenant_demo",
            "session_id": "smoke-test-hotel-001",
            "user_message": "Yes, book this hotel.",
            "messages": [HumanMessage(content="Yes, book this hotel.")],
            "booking": {
                "booking_id": old_after.booking_id,
                "user_id": old_after.user_id,
                "tenant_id": old_after.tenant_id,
                "session_id": old_after.session_id,
                "hotel_id": old_after.hotel_id,
                "status": old_after.status,
            },
            "hotel_options": [hotel],
        },
        context=GraphContext(db=test_db),
    )
    cancelled_answer = cancelled_retry["messages"][-1].content.lower()
    assert cancelled_retry["booking"]["status"] == "cancelled"
    assert cancelled_retry["pending_booking_confirmation"] is False
    assert "already confirmed" not in cancelled_answer
    assert "hotel booking is cancelled" in cancelled_answer
    assert "status: cancelled" in cancelled_answer


def test_compiled_transport_confirmation_retry_returns_existing_booking(test_db):
    test_db.add(Tenant(tenant_id="tenant_demo", name="Demo", slug="demo"))
    test_db.commit()
    option = _transport_option()

    class Memory:
        def get_messages(self, session_id, tenant_id):
            return []

    class Perception:
        def understand(self, message, history):
            return TripPerception(
                intent="book_trip",
                destination="B",
                travellers=1,
                selected_option_id="TRAIN-1",
                confirmation="yes",
            )

    graph = TravelAgentGraph()
    graph.memory = Memory()
    graph.perception_agent = Perception()
    state = {
        "user_message": "Yes, book this option.",
        "user_id": "same-user-id",
        "tenant_id": "tenant_demo",
        "session_id": "transport-retry-test",
        "messages": [HumanMessage(content="Yes, book this option.")],
        "perception": None,
        "plan": None,
        "destination_resolution": None,
        "clarification_needed": False,
        "pending_clarification": None,
        "pending_destination": None,
        "pending_destination_candidates": [],
        "tool_context": None,
        "trip_context": None,
        "transport_options": [option],
        "hotel_options": [],
        "hotel_search_performed": False,
        "transport_search_performed": False,
        "selected_option_id": "TRAIN-1",
        "pending_booking_confirmation": True,
        "pending_booking_domain": "transport",
        "pending_cancellation_booking_id": None,
        "booking": None,
        "answer": None,
    }

    first = graph.graph.invoke(state, context=GraphContext(db=test_db))
    booking_id = first["booking"]["booking_id"]
    assert first["booking"]["status"] == "confirmed"
    assert first["pending_booking_confirmation"] is False

    retry = graph.graph.invoke(
        {
            **first,
            "user_message": "Yes, book this option.",
            "messages": [HumanMessage(content="Yes, book this option.")],
        },
        context=GraphContext(db=test_db),
    )
    answer = retry["messages"][-1].content
    assert retry["booking"]["booking_id"] == booking_id
    assert retry["booking"]["status"] == "confirmed"
    assert retry["pending_booking_confirmation"] is False
    assert retry["selected_option_id"] is None
    assert "already confirmed" in answer.lower()
    assert "Do you want me to book this option?" not in answer
    assert test_db.query(Booking).filter_by(session_id="transport-retry-test").count() == 1

    BookingService(test_db).cancel_booking(
        booking_id, "same-user-id", "tenant_demo"
    )
    cancelled = graph.graph.invoke(
        {
            **first,
            "user_message": "Yes, book this option.",
            "messages": [HumanMessage(content="Yes, book this option.")],
        },
        context=GraphContext(db=test_db),
    )
    cancelled_answer = cancelled["messages"][-1].content.lower()
    assert cancelled["booking"]["status"] == "cancelled"
    assert cancelled["pending_booking_confirmation"] is False
    assert "already confirmed" not in cancelled_answer
    assert "status: cancelled" in cancelled_answer


def test_repeated_transport_confirmation_reuses_existing_cross_session_booking(test_db):
    test_db.add(Tenant(tenant_id="tenant_demo", name="Demo", slug="demo"))
    test_db.commit()
    option = _transport_option()
    existing = BookingService(test_db).create_booking(
        _transport_request("tenant_demo").model_copy(
            update={"user_id": "user_demo", "session_id": "transport-booking-live-001", "travellers": 2}
        ),
        {**option, "price": 4200.0},
    )

    class Memory:
        def get_messages(self, session_id, tenant_id):
            return []

    class Perception:
        def understand(self, message, history):
            assert message == "Yes, confirm and book it."
            return TripPerception(
                intent="book_trip",
                destination="B",
                travellers=2,
                selected_option_id="TRAIN-1",
                confirmation="yes",
            )

    graph = TravelAgentGraph()
    graph.memory = Memory()
    graph.perception_agent = Perception()
    state = {
        "user_message": "Yes, confirm and book it.",
        "user_id": "user_demo",
        "tenant_id": "tenant_demo",
        "session_id": "transport-retry-live-001",
        "messages": [HumanMessage(content="Yes, confirm and book it.")],
        "perception": None,
        "plan": None,
        "destination_resolution": None,
        "clarification_needed": False,
        "pending_clarification": None,
        "pending_destination": None,
        "pending_destination_candidates": [],
        "tool_context": None,
        "trip_context": None,
        "transport_options": [{**option, "price": 4200.0}],
        "hotel_options": [],
        "hotel_search_performed": False,
        "transport_search_performed": False,
        "selected_option_id": "TRAIN-1",
        "pending_booking_confirmation": False,
        "pending_booking_domain": "transport",
        "pending_cancellation_booking_id": None,
        "booking": existing.model_dump(mode="json"),
        "answer": None,
    }

    first = graph.graph.invoke(state, context=GraphContext(db=test_db))
    second = graph.graph.invoke(
        {
            **first,
            "user_message": "Yes, confirm and book it.",
            "messages": [HumanMessage(content="Yes, confirm and book it.")],
        },
        context=GraphContext(db=test_db),
    )

    for response in (first, second):
        answer = response["messages"][-1].content.lower()
        assert response["booking"]["booking_id"] == existing.booking_id
        assert response["booking"]["status"] == "confirmed"
        assert response["pending_booking_confirmation"] is False
        assert response["selected_option_id"] is None
        assert response["pending_booking_domain"] == "transport"
        assert "already confirmed" in answer
        assert "do you want me to book this option?" not in answer

    assert test_db.query(Booking).filter_by(
        user_id="user_demo", tenant_id="tenant_demo", option_id="TRAIN-1"
    ).count() == 1


def test_unified_booking_query_service_returns_both_domains_and_is_tenant_scoped(
    db_session_factory,
):
    with db_session_factory() as db:
        transport = BookingService(db).create_booking(
            _transport_request("tenant_a"), _transport_option()
        )
        hotel = HotelBookingService(db).create_booking(
            _hotel_request("tenant_a"), _selected_hotel()
        )
        facade = BookingQueryService(db)

        assert facade.get_booking(
            transport.booking_id, "same-user-id", "tenant_a"
        )["booking_domain"] == "transport"
        assert facade.get_booking(
            hotel.booking_id, "same-user-id", "tenant_a"
        )["booking_domain"] == "hotel"
        assert {item["booking_domain"] for item in facade.get_user_bookings(
            "same-user-id", "tenant_a"
        )} == {"transport", "hotel"}
        with pytest.raises(ValueError, match="not found"):
            facade.get_booking(transport.booking_id, "same-user-id", "tenant_b")


def test_booking_api_retrieves_transport_and_keeps_hotel_available(db_session_factory):
    from fastapi.testclient import TestClient

    from app.auth.dependencies import get_current_user
    from app.core.tenant_context import TenantContext
    from app.database.connection import get_db
    from app.main import app

    with db_session_factory() as db:
        transport = BookingService(db).create_booking(
            _transport_request("tenant_a"), _transport_option()
        )
        hotel = HotelBookingService(db).create_booking(
            _hotel_request("tenant_a"), _selected_hotel()
        )

        def override_db():
            yield db

        tenant = {"id": "tenant_a"}

        def override_user():
            return TenantContext(user_id="same-user-id", tenant_id=tenant["id"])

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        try:
            with TestClient(app) as client:
                transport_response = client.get(
                    f"/api/v1/bookings/{transport.booking_id}"
                )
                hotel_response = client.get(f"/api/v1/bookings/{hotel.booking_id}")
                list_response = client.get("/api/v1/bookings")
                tenant["id"] = "tenant_b"
                foreign_response = client.get(
                    f"/api/v1/bookings/{transport.booking_id}"
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert transport_response.status_code == 200
    assert transport_response.json()["booking_domain"] == "transport"
    assert hotel_response.status_code == 200
    assert hotel_response.json()["booking_domain"] == "hotel"
    assert list_response.status_code == 200
    assert {item["booking_domain"] for item in list_response.json()["bookings"]} == {
        "transport",
        "hotel",
    }
    assert foreign_response.status_code == 404
