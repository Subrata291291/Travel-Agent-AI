from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.tenant_context import TenantContext
from app.database.connection import get_db
from app.services.booking_query_service import BookingQueryService


router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
)


@router.get("")
def get_my_bookings(
    context: TenantContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all transport and hotel bookings belonging to the
    authenticated user inside the current tenant.

    Database ownership:

        FastAPI
            ↓
        get_db()
            ↓
        SQLAlchemy Session
            ↓
        BookingQueryService
            ↓
        Domain booking services and repositories
    """

    service = BookingQueryService(db)

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


@router.get("/{booking_id}")
def get_booking(
    booking_id: str,
    context: TenantContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return one transport or hotel booking belonging to the
    authenticated user inside the current tenant.
    """

    service = BookingQueryService(db)

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


@router.post("/{booking_id}/cancel")
def cancel_booking(
    booking_id: str,
    context: TenantContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel one transport or hotel booking belonging to the
    authenticated user inside the current tenant.
    """

    service = BookingQueryService(db)

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
