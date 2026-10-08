from sqlalchemy.orm import Session

from app.schemas.booking import BookingRequest
from app.services.booking_service import BookingService


def book_transport(
    db: Session,
    user_id: str,
    tenant_id: str,
    session_id: str,
    option_id: str,
    travellers: int = 1,
    mode: str = "",
    provider: str = "",
    origin: str = "",
    destination: str = "",
    departure_time: str = "",
    arrival_time: str = "",
    duration_minutes: int = 0,
    price: float = 0,
    currency: str = "INR",
) -> dict:
    """
    Create a confirmed transport booking.

    IMPORTANT:
    This tool must NOT be exposed to the normal autonomous LLM
    tool list.

    The application should call the booking service only after:

        1. A transport option was selected.
        2. The option exists in persisted state.
        3. The user explicitly confirmed the booking.

    Role:
    - Provides a structured boundary around BookingService.
    - Converts the result into a JSON-compatible dictionary.
    """

    selected_option = {
        "option_id": option_id,
        "mode": mode,
        "provider": provider,
        "origin": origin,
        "destination": destination,
        "departure_time": departure_time,
        "arrival_time": arrival_time,
        "duration_minutes": duration_minutes,
        "price": price,
        "currency": currency,
    }

    request = BookingRequest(
        user_id=user_id,
        tenant_id=tenant_id,
        session_id=session_id,
        option_id=option_id,
        travellers=travellers,
    )

    response = BookingService(db).create_booking(
        request=request,
        selected_option=selected_option,
    )

    return response.model_dump(
        mode="json"
    )
