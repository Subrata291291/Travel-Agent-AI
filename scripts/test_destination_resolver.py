from app.tools.destination_resolver import (
    DestinationResolver,
)


def main():

    resolver = DestinationResolver()

    result = resolver.resolve(
        "Manali"
    )

    print("\n==============================")
    print("DESTINATION RESOLUTION")
    print("==============================\n")

    print("Status:")
    print(result["status"])

    print("\nOriginal location:")
    print(result["location"])

    print("\nCandidates:")

    for index, candidate in enumerate(
        result["candidates"],
        start=1,
    ):
        print(
            f"\nCandidate {index}:"
        )

        print(
            f"  Name: {candidate['name']}"
        )

        print(
            f"  Country: {candidate['country']}"
        )

        print(
            f"  Region: {candidate['admin1']}"
        )

        print(
            f"  Latitude: {candidate['latitude']}"
        )

        print(
            f"  Longitude: {candidate['longitude']}"
        )


if __name__ == "__main__":
    main()