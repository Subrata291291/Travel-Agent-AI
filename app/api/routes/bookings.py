from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.tenant_context import TenantContext
from app.database.connection import get_db
from app.schemas.hotel_booking import (
    HotelBookingListResponse,
    HotelBookingResponse,
)
from app.services.hotel_booking_service import HotelBookingService


router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
)


@router.get(
    "",
    response_model=HotelBookingListResponse,
)
def get_my_bookings(
    context: TenantContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all hotel bookings belonging to the
    authenticated user inside the current tenant.

    Database ownership:

        FastAPI
            ↓
        get_db()
            ↓
        SQLAlchemy Session
            ↓
        HotelBookingService
            ↓
        HotelBookingRepository
    """

    service = HotelBookingService(db)

    try:
        bookings = service.get_user_bookings(
            user_id=context.user_id,
            tenant_id=context.tenant_id,
        )

        return {
            "user_id": context.user_id,
            "tenant_id": context.tenant_id,
            "count": len(bookings),
            "bookings": bookings,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get(
    "/{booking_id}",
    response_model=HotelBookingResponse,
)
def get_booking(
    booking_id: str,
    context: TenantContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return one hotel booking belonging to the
    authenticated user inside the current tenant.
    """

    service = HotelBookingService(db)

    try:
        return service.get_booking(
            booking_id=booking_id,
            user_id=context.user_id,
            tenant_id=context.tenant_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{booking_id}/cancel",
    response_model=HotelBookingResponse,
)
def cancel_booking(
    booking_id: str,
    context: TenantContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel one hotel booking belonging to the
    authenticated user inside the current tenant.
    """

    service = HotelBookingService(db)

    try:
        return service.cancel_booking(
            booking_id=booking_id,
            user_id=context.user_id,
            tenant_id=context.tenant_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc