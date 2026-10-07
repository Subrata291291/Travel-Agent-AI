from app.services.booking_service import BookingService


def main():
    service = BookingService()

    booking_id = "BOOK-29F06E436FF9"
    user_id = "user_001"
    tenant_id = "tenant_demo"

    print("\n===== CANCELLING BOOKING =====")

    result = service.cancel_booking(
        booking_id=booking_id,
        user_id=user_id,
        tenant_id=tenant_id,
    )

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
