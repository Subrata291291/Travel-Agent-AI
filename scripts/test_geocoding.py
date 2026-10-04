from app.tools.geocoding import GeocodingTool


def main():

    tool = GeocodingTool()

    result = tool.search("Manali")

    print("\n==============================")
    print("GEOCODING RESULT")
    print("==============================\n")

    print(result)


if __name__ == "__main__":
    main()