from app.tools.weather import WeatherTool


def main():

    weather_tool = WeatherTool()

    result = weather_tool.get_weather(
        "Manali"
    )

    print("\n==============================")
    print("MANALI WEATHER")
    print("==============================\n")

    print(result)


if __name__ == "__main__":
    main()