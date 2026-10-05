from app.services.booking_service import BookingService


def main():

    print("=" * 60)
    print("BOOKING RETRIEVAL TEST")
    print("=" * 60)

    service = BookingService()

    bookings = service.get_user_bookings(
        user_id="user_001"
    )

    print()
    print(
        f"Total bookings found: {len(bookings)}"
    )

    print()

    for booking in bookings:

        print("-" * 60)

        print(
            f"Booking ID : {booking.booking_id}"
        )

        print(
            f"Option     : {booking.option_id}"
        )

        print(
            f"Mode       : {booking.mode}"
        )

        print(
            f"From       : {booking.origin}"
        )

        print(
            f"To         : {booking.destination}"
        )

        print(
            f"Travellers : {booking.travellers}"
        )

        print(
            f"Total      : "
            f"{booking.total_price} "
            f"{booking.currency}"
        )

        print(
            f"Status     : {booking.status}"
        )

        print(
            f"Created    : {booking.created_at}"
        )


if __name__ == "__main__":
    main()