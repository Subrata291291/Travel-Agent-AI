import asyncio

from app.providers.duffel.client import DuffelClient, DuffelAPIError


async def main():
    try:
        client = DuffelClient()

        # Simple API request to verify authentication.
        response = await client.get("/air/airports")

        print("✅ Duffel connection successful!")
        print("Response received from Duffel.")

        # Print only a small part of the response.
        data = response.get("data", [])

        print(f"Airports returned: {len(data)}")

        if data:
            print("First airport:")
            print(data[0])

    except DuffelAPIError as exc:
        print("❌ Duffel API error:")
        print(exc)

        if exc.status_code:
            print(f"HTTP status: {exc.status_code}")

    except Exception as exc:
        print("❌ Unexpected error:")
        print(type(exc).__name__)
        print(exc)


if __name__ == "__main__":
    asyncio.run(main())