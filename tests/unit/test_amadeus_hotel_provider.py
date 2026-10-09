from datetime import date, timedelta

import httpx
import pytest

from app.providers.amadeus.client import AmadeusClient
from app.providers.amadeus.hotels import AmadeusHotelProvider
from app.providers.errors import ProviderRequestError


def test_amadeus_search_preserves_supplier_offer_and_price(monkeypatch):
    from app.config import settings as settings_module
    monkeypatch.setattr(settings_module.settings, "amadeus_client_id", "test-id")
    monkeypatch.setattr(settings_module.settings, "amadeus_client_secret", "test-secret")
    today = date.today()

    def respond(request):
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "test-token"})
        if request.url.path.endswith("/hotels/by-geocode"):
            assert request.url.params["latitude"] == "48.8"
            return httpx.Response(200, json={"data": [{"hotelId": "HLPAR1", "name": "Test Hotel"}]})
        if request.url.path.endswith("/hotel-offers"):
            assert request.headers["Authorization"] == "Bearer test-token"
            assert request.url.params["checkInDate"] == (today + timedelta(days=30)).isoformat()
            assert request.url.params["roomQuantity"] == "2"
            return httpx.Response(200, json={"data": [{"hotel": {"hotelId": "HLPAR1", "name": "Test Hotel"},
                "offers": [{"id": "OFFER-77", "price": {"total": "300", "currency": "EUR"},
                            "room": {"typeEstimated": {"category": "STANDARD"}}, "boardType": "BREAKFAST"}]}]})
        raise AssertionError(request.url)

    provider = AmadeusHotelProvider(client=AmadeusClient(
        client_id="test-id", client_secret="test-secret",
        transport=httpx.MockTransport(respond), sleep=lambda _delay: None,
    ))
    options = provider.search_hotels("PAR", (today + timedelta(days=30)).isoformat(),
                                     (today + timedelta(days=32)).isoformat(), currency="EUR",
                                     resolved_destination={"latitude": 48.8, "longitude": 2.3},
                                     room_quantity=2)
    assert len(options) == 1
    assert options[0].supplier_offer_id == "OFFER-77"
    assert options[0].supplier_hotel_id == "HLPAR1"
    assert options[0].total_price == 300
    assert options[0].price_per_night == 150
    assert options[0].provider_details["room_type"] == "STANDARD"


def test_amadeus_is_disabled_without_credentials(monkeypatch):
    from app.config import settings as settings_module
    monkeypatch.setattr(settings_module.settings, "amadeus_client_id", "")
    monkeypatch.setattr(settings_module.settings, "amadeus_client_secret", "")
    with pytest.raises(RuntimeError, match="not configured"):
        AmadeusHotelProvider().client.get("/v1/reference-data/locations/hotels/by-geocode", {})


def test_optional_provider_settings_default_to_safe_disabled_test_config():
    from app.config.settings import Settings
    config = Settings(_env_file=None, jwt_secret_key="unit-test")
    assert config.amadeus_client_id == ""
    assert config.amadeus_client_secret == ""
    assert config.amadeus_base_url == "https://test.api.amadeus.com"
    assert config.busbud_api_key == ""
    assert config.busbud_base_url == ""


def test_amadeus_client_retries_rate_limits():
    calls = {"count": 0}
    delays = []

    def respond(request):
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "test-token"})
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"data": []})

    client = AmadeusClient(
        client_id="test-id", client_secret="test-secret",
        transport=httpx.MockTransport(respond), sleep=delays.append,
    )
    assert client.get("/search", {}) == {"data": []}
    assert calls["count"] == 3
    assert len(delays) == 2


def test_amadeus_client_retries_timeout_and_returns_sanitized_error():
    calls = {"count": 0}

    def timeout(_request):
        calls["count"] += 1
        raise httpx.ReadTimeout("private request details")

    client = AmadeusClient(
        client_id="test-id", client_secret="test-secret",
        transport=httpx.MockTransport(timeout), sleep=lambda _delay: None,
    )
    with pytest.raises(ProviderRequestError, match="timed out") as error:
        client.get("/search", {})
    assert calls["count"] == client.max_attempts
    assert "private request details" not in str(error.value)


def test_busbud_and_train_search_are_disabled_without_supported_access():
    from app.providers.busbud_adapter import BusbudProvider
    from app.tools.trains import search_trains
    with pytest.raises(RuntimeError, match="disabled"):
        BusbudProvider().search_buses(origin="A", destination="B", departure_date="2030-01-01")
    with pytest.raises(RuntimeError, match="authorized"):
        search_trains.invoke({"origin": "A", "destination": "B", "departure_date": "2030-01-01"})


def test_amadeus_retries_rate_limit_using_retry_after():
    calls = []
    delays = []

    def respond(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        hotel_list_calls = sum(path.endswith("/hotels/by-geocode") for path in calls)
        if hotel_list_calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={})
        return httpx.Response(200, json={"data": []})

    client = AmadeusClient(
        client_id="id", client_secret="secret",
        transport=httpx.MockTransport(respond), sleep=delays.append,
    )
    provider = AmadeusHotelProvider(client=client)
    start = date.today() + timedelta(days=30)
    assert provider.search_hotels(
        "Paris", start.isoformat(), (start + timedelta(days=1)).isoformat(),
        resolved_destination={"latitude": 48.8, "longitude": 2.3},
    ) == []
    assert sum(path.endswith("/hotels/by-geocode") for path in calls) == 2
    assert delays == [0.0]
