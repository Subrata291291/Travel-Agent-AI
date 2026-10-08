
from app.providers.duffel.flights import DuffelFlightProvider
from app.providers.duffel.client import DuffelAPIError


def main():
    provider = DuffelFlightProvider()

    try:
        print("Searching Duffel flights...")
        print("Route: CCU → DEL")
        print("Passengers: 1")
        print()

        options = provider.search_flights(
            origin="CCU",
            destination="DEL",
            departure_date="2026-12-20",
            travellers=1,
        )

        print(f"Flights returned: {len(options)}")
        print("=" * 80)

        for index, option in enumerate(options, start=1):
            print(f"\nFlight {index}")
            print(f"Option ID : {option.option_id}")
            print(f"Provider  : {option.provider}")
            print(f"Route     : {option.origin} → {option.destination}")
            print(f"Departure : {option.departure_time}")
            print(f"Arrival   : {option.arrival_time}")
            print(f"Duration  : {option.duration_minutes} minutes")
            print(f"Price     : {option.price} {option.currency}")

    except DuffelAPIError as exc:
        print("❌ Duffel API error")
        print(exc)

        if exc.status_code:
            print(f"HTTP status: {exc.status_code}")

    except Exception as exc:
        print("❌ Unexpected error")
        print(type(exc).__name__)
        print(exc)


if __name__ == "__main__":
    main()