"""Tenant-scoped facade for the transport and hotel booking stores."""

from app.services.booking_service import BookingService
from app.services.hotel_booking_service import HotelBookingService


class BookingQueryService:
    """Provide one booking API view while retaining domain services."""

    def __init__(self, db):
        self.transport = BookingService(db)
        self.hotel = HotelBookingService(db)

    @staticmethod
    def _record(domain: str, booking) -> dict:
        return {"booking_domain": domain, **booking.model_dump(mode="json")}

    def get_user_bookings(self, user_id: str, tenant_id: str) -> list[dict]:
        bookings = [
            self._record("transport", booking)
            for booking in self.transport.get_user_bookings(user_id, tenant_id)
        ]
        bookings.extend(
            self._record("hotel", booking)
            for booking in self.hotel.get_user_bookings(user_id, tenant_id)
        )
        return bookings

    def get_booking(self, booking_id: str, user_id: str, tenant_id: str) -> dict:
        for domain, service in (("transport", self.transport), ("hotel", self.hotel)):
            try:
                return self._record(
                    domain,
                    service.get_booking(booking_id, user_id, tenant_id),
                )
            except ValueError:
                continue
        raise ValueError(f"Booking {booking_id} was not found.")

    def cancel_booking(self, booking_id: str, user_id: str, tenant_id: str) -> dict:
        # IDs share a format across domains, so resolve ownership before cancelling.
        for domain, service in (("transport", self.transport), ("hotel", self.hotel)):
            try:
                service.get_booking(booking_id, user_id, tenant_id)
            except ValueError:
                continue
            return self._record(
                domain,
                service.cancel_booking(booking_id, user_id, tenant_id),
            )
        raise ValueError(f"Booking {booking_id} was not found.")
