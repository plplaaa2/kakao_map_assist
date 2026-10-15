"""Verify future-driving selection and forecast dates; related files: api.py, llm.py."""

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import probatio as vol
import pytest
import pytest_asyncio
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import llm

import custom_components.kakaomap as integration
from custom_components.kakaomap import api
from tests.test_car_routes import CAR
from tests.test_llm import context
from tests.test_route_extensions import STOPS
from tests.test_routes import COORDINATES, route_server  # noqa: F401

NOW = datetime(2026, 10, 15, tzinfo=UTC)
FUTURE = "2026-10-16T08:00:00+09:00"


@pytest_asyncio.fixture
async def future_server(route_server, monkeypatch):
    """Reuse loopback with a distinct future endpoint and fixed reference clock."""
    client, state = route_server
    client._time_zone = ZoneInfo("Asia/Seoul")
    state["payload"] = deepcopy(CAR)
    monkeypatch.setattr(api, "FUTURE_ROUTE_URL", api.ROUTE_URLS["car"].replace("/car", "/future"))
    clock = Mock(wraps=datetime)
    clock.now.return_value = NOW
    monkeypatch.setattr(api, "datetime", clock)
    return client, state


async def test_future_endpoint_departure_and_arrival(future_server):
    client, state = future_server
    result = await client.async_get_route(**COORDINATES, mode="car", departure_time=FUTURE)
    assert state["path"] == "/future" and state["authenticated"]
    assert state["query"]["departure_time"] == "202610160800"
    assert state["query"]["priority"] == "RECOMMEND" and state["query"]["alternatives"] == "false"
    assert result["is_future"]
    assert result["requested_at"] == "2026-10-15T09:00:00+09:00"
    assert result["departure_time"] == FUTURE
    assert result["routes"][0]["arrival_time"] == "2026-10-16T08:30:00+09:00"


async def test_omitted_departure_keeps_current_endpoint(future_server):
    client, state = future_server
    result = await client.async_get_route(**COORDINATES, mode="car")
    assert state["path"] == "/car" and "departure_time" not in state["query"]
    assert not result["is_future"]
    assert result["departure_time"] == "2026-10-15T09:00:00+09:00"


@pytest.mark.parametrize("departure", ["2026-10-15T23:00:00Z", "2026-10-16T01:00:00+02:00"])
async def test_input_offsets_refer_to_same_korean_departure(future_server, departure):
    client, state = future_server
    result = await client.async_get_route(**COORDINATES, mode="car", departure_time=departure)
    assert state["query"]["departure_time"] == "202610160800"
    assert result["departure_time"] == FUTURE


async def test_ha_display_zone_differs_from_request_zone(future_server):
    client, state = future_server
    client._time_zone = ZoneInfo("America/New_York")
    result = await client.async_get_route(**COORDINATES, mode="car", departure_time=FUTURE)
    assert state["query"]["departure_time"] == "202610160800"
    assert result["time_zone"] == "America/New_York"
    assert result["departure_time"] == "2026-10-15T19:00:00-04:00"
    assert result["routes"][0]["arrival_time"] == "2026-10-15T19:30:00-04:00"


async def test_future_midnight_waypoints_and_alternatives(future_server):
    client, state = future_server
    alternative = deepcopy(CAR["routes"][0])
    alternative["summary"].update(priority="TIME", duration=2400, fare={"toll": 0})
    state["payload"]["routes"][0]["summary"]["priority"] = "TIME"
    state["payload"]["routes"].append(alternative)
    result = await client.async_get_route(**COORDINATES, mode="car",
        departure_time="2026-10-16T23:50:00+09:00", priority="TIME", avoid=["toll"],
        waypoints=STOPS, alternatives=True)
    assert state["query"]["waypoints"] == "127.12,37.4|127.13,37.41"
    assert state["query"]["alternatives"] == "true" and state["query"]["avoid"] == "toll"
    assert result["routes"][0]["arrival_time"] == "2026-10-17T00:20:00+09:00"
    assert result["routes"][1]["arrival_time"] == "2026-10-17T00:30:00+09:00"
    assert result["routes"][1]["difference_from_primary"]["duration_s"] == 600


@pytest.mark.parametrize("departure", [
    "", " ", "tomorrow 8am", "202610160800", "2026-10-16", "2026-10-16T08:00:00",
    "2026-02-30T08:00:00+09:00", "2026-10-15T09:00:00+09:00",
    "2026-10-14T08:00:00+09:00", "2026-10-16T08:00:01+09:00",
    "2026-10-16T08:00:00.001+09:00", "2026-10-16T08:00:00+09:00:30",
    "9999-12-31T23:59:00Z", True, 123,
])
async def test_invalid_departure_never_calls_http(future_server, departure):
    client, state = future_server
    with pytest.raises(ValueError):
        await client.async_get_route(**COORDINATES, mode="car", departure_time=departure)
    assert "query" not in state


@pytest.mark.parametrize("mode", ["public_transport", "walk", "bicycle"])
async def test_future_is_car_only(future_server, mode):
    client, state = future_server
    with pytest.raises(ValueError):
        await client.async_get_route(**COORDINATES, mode=mode, departure_time=FUTURE)
    assert "query" not in state


async def test_assist_future_roundtrip(future_server, hass, entry, monkeypatch):
    client, state = future_server
    monkeypatch.setattr(hass.config, "time_zone", "Asia/Seoul")
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    instance = await llm.async_get_api(hass, f"kakaomap-{entry.entry_id}", context())
    result = await instance.async_call_tool(llm.ToolInput(tool_name="kakaomap__get_route", tool_args={
        **COORDINATES, "mode": "car", "departure_time": FUTURE,
    }))
    assert result.data["is_future"] and state["path"] == "/future"
    assert result.data["departure_time"] == FUTURE
    assert "Current HA time:" in instance.api_prompt
    assert "ask if date/time is ambiguous" in instance.api_prompt


@pytest.mark.parametrize("status,message", [(401, "인증"), (403, "권한"),
                                            (429, "한도"), (500, "연결")])
async def test_future_http_errors_without_current_fallback(future_server, hass, entry, monkeypatch, status, message):
    client, state = future_server
    state["status"] = status
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    notify, reauth = Mock(), Mock()
    monkeypatch.setattr(integration, "async_notify_auth_failure", notify)
    monkeypatch.setattr(type(entry), "async_start_reauth", reauth)
    await integration.async_setup_entry(hass, entry)
    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call("kakaomap", "get_route",
            {**COORDINATES, "mode": "car", "departure_time": FUTURE}, blocking=True, return_response=True)
    assert state["path"] == "/future"
    assert notify.call_count == reauth.call_count == (1 if status == 401 else 0)


@pytest.mark.parametrize("options", [{"departure_time": ""}, {"departure_time": True},
    {"departure_time": "2026-10-16T08:00"}, {"mode": "public_transport", "departure_time": FUTURE}])
async def test_action_validation_before_http(future_server, hass, entry, monkeypatch, options):
    client, state = future_server
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    with pytest.raises((vol.Invalid, ServiceValidationError)):
        await hass.services.async_call("kakaomap", "get_route",
            {**COORDINATES, "mode": "car", **options}, blocking=True, return_response=True)
    assert "query" not in state
