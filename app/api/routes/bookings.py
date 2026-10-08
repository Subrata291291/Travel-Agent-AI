from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.core.tenant_context import TenantContext
from app.schemas.hotel_booking import (
    HotelBookingListResponse,
    HotelBookingResponse,
)
from app.services.hotel_booking_service import HotelBookingService


router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
)


hotel_booking_service = HotelBookingService()


@router.get(
    "",
    response_model=HotelBookingListResponse,
)
def get_my_bookings(
    context: TenantContext = Depends(get_current_user)
):
    """
    Return all hotel bookings belonging to the
    authenticated user inside the current tenant.
    """

    try:
        bookings = hotel_booking_service.get_user_bookings(
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
):
    """
    Return one hotel booking belonging to the
    authenticated user inside the current tenant.
    """

    try:
        return hotel_booking_service.get_booking(
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
):
    try:
        return hotel_booking_service.cancel_booking(
            booking_id=booking_id,
            user_id=context.user_id,
            tenant_id=context.tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc