import pytest

from app.agents.graph import TravelAgentGraph
from app.providers.duffel.airports import AirportResolver
from app.providers.duffel.flights import DuffelFlightProvider
from app.schemas.perception import TripPerception


class FakeDuffelClient:
    def __init__(self, places=None, offers=None):
        self.places = places or {}
        self.offers = offers or []
        self.get_calls = []
        self.post_calls = []

    def get_sync(self, path, params=None):
        self.get_calls.append((path, params))
        query = (params or {}).get("query")
        return {"data": self.places.get(query, self.places.get("nearby", []))}

    def post_sync(self, path, json=None):
        self.post_calls.append((path, json))
        return {"data": {"offers": self.offers}}


def test_airport_resolver_validates_iata_codes_using_duffel_data():
    client = FakeDuffelClient(places={
        "ccu": [{"type": "airport", "name": "Netaji Subhas Chandra Bose International Airport", "iata_code": "CCU", "city_name": "Kolkata", "iata_country_code": "IN"}]
    })
    resolver = AirportResolver(client)

    assert resolver.resolve(" ccu ") == "CCU"
    assert client.get_calls == [("/places/suggestions", {"query": "ccu"})]


def test_howrah_resolves_through_duffel_kolkata_airport_data():
    client = FakeDuffelClient(places={
        "Howrah": [],
        "nearby": [{
            "type": "airport", "id": "arp_ccu_in",
            "name": "Netaji Subhas Chandra Bose International Airport",
            "iata_code": "CCU", "city_name": "Kolkata", "iata_country_code": "IN",
        }],
    })
    class HowrahGeocoder:
        def search(self, _query):
            return {"latitude": 22.5958, "longitude": 88.2636}

    result = AirportResolver(client, geocoding=HowrahGeocoder()).lookup("Howrah", field="origin")
    assert result == {
        "status": "resolved",
        "airport_name": "Netaji Subhas Chandra Bose International Airport",
        "city": "Kolkata",
        "country_code": "IN",
        "iata_code": "CCU",
        "duffel_place_id": "arp_ccu_in",
    }
    assert client.get_calls[1][1] == {
        "lat": "22.5958", "lng": "88.2636", "rad": "60000"
    }


def test_kolkata_resolves_to_ccu_from_authoritative_duffel_response():
    client = FakeDuffelClient(places={
        "Kolkata": [{
            "type": "airport", "name": "Netaji Subhas Chandra Bose International Airport",
            "iata_code": "CCU", "city_name": "Kolkata", "iata_country_code": "IN",
        }]
    })
    assert AirportResolver(client).resolve("Kolkata") == "CCU"


def test_airport_resolver_never_invents_code_when_lookup_has_no_results():
    client = FakeDuffelClient()
    with pytest.raises(ValueError, match="No airport or city code found"):
        AirportResolver(client).resolve("Not a real airport")


def test_airport_resolver_reports_lookup_service_unavailable():
    from app.providers.duffel.client import DuffelAPIError

    class OfflineClient:
        def get_sync(self, *_args, **_kwargs):
            raise DuffelAPIError("offline")

    with pytest.raises(ValueError, match="temporarily unavailable"):
        AirportResolver(OfflineClient()).lookup("Kolkata")


def test_airport_resolver_uses_exact_city_code_for_multi_airport_city():
    client = FakeDuffelClient(
        places={
            "New York": [
                {"type": "airport", "name": "JFK", "iata_code": "JFK"},
                {"type": "city", "name": "New York", "iata_code": "NYC"},
                {"type": "airport", "name": "LaGuardia", "iata_code": "LGA"},
            ]
        }
    )

    assert AirportResolver(client).resolve("New York") == "NYC"
    assert client.get_calls == [
        ("/places/suggestions", {"query": "New York"})
    ]


def test_airport_resolver_requires_clarification_for_ambiguous_airports():
    client = FakeDuffelClient(
        places={
            "Springfield": [
                {"type": "airport", "name": "Springfield A", "iata_code": "AAA"},
                {"type": "airport", "name": "Springfield B", "iata_code": "BBB"},
            ]
        }
    )

    with pytest.raises(ValueError, match="matches multiple airports") as error:
        AirportResolver(client).resolve("Springfield")
    assert "Which airport would you like?" in str(error.value)


def test_duffel_provider_resolves_city_names_and_preserves_offer_id():
    offer = {
        "id": "off_live_123",
        "total_amount": "128.50",
        "total_currency": "USD",
        "slices": [
            {
                "segments": [
                    {
                        "departing_at": "2027-03-01T10:00:00Z",
                        "arriving_at": "2027-03-01T11:00:00Z",
                        "origin": {"iata_code": "CCU"},
                        "destination": {"iata_code": "DEL"},
                        "operating_carrier": {"name": "Example Air"},
                    }
                ]
            }
        ],
    }
    client = FakeDuffelClient(
        places={
            "Kolkata": [{"type": "city", "name": "Kolkata", "iata_code": "CCU"}],
            "Delhi": [{"type": "city", "name": "Delhi", "iata_code": "DEL"}],
        },
        offers=[offer],
    )

    options = DuffelFlightProvider(client).search_flights(
        origin="Kolkata",
        destination="Delhi",
        departure_date="2027-03-01",
        travellers=2,
    )

    assert len(options) == 1
    assert options[0].option_id == "off_live_123"
    assert options[0].origin == "CCU"
    assert options[0].destination == "DEL"
    assert options[0].travellers == 2
    assert options[0].price == 64.25
    assert options[0].total_price == 128.5
    payload = client.post_calls[0][1]
    assert payload["data"]["slices"][0]["origin"] == "CCU"
    assert payload["data"]["slices"][0]["destination"] == "DEL"


def test_graph_routes_provider_generated_flight_id_as_transport_booking():
    graph = TravelAgentGraph()
    route = graph.perception_route(
        {
            "perception": TripPerception(
                intent="book_trip",
                selected_option_id="off_live_123",
            ),
            "transport_options": [
                {"option_id": "off_live_123", "mode": "flight"}
            ],
            "pending_booking_confirmation": False,
            "booking": None,
        }
    )

    assert route == "transport_existing_booking"


def test_graph_surfaces_airport_ambiguity_in_chat_answer():
    graph = TravelAgentGraph.__new__(TravelAgentGraph)
    result = graph.structured_options_node(
        {
            "transport_search_performed": True,
            "transport_search_error": (
                "'Springfield' matches multiple places: Springfield A (AAA), "
                "Springfield B (BBB). Please specify the city or airport."
            ),
            "transport_options": [],
            "hotel_search_performed": False,
        }
    )

    assert "Springfield A (AAA)" in result["messages"][0].content
    assert "Please specify the city or airport" in result["messages"][0].content
