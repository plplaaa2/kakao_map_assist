"""Verify route HTTP and HA contracts; related files: api.py, routes.py, __init__.py."""

import asyncio
from copy import deepcopy
from unittest.mock import Mock

import aiohttp
from aiohttp import web
import pytest
import pytest_asyncio
import probatio as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

import custom_components.kakaomap as integration
from custom_components.kakaomap import api

COORDINATES = {
    "start_latitude": 37.3947766, "start_longitude": 127.1111967,
    "end_latitude": 37.4199324, "end_longitude": 127.1262904,
}
WALK = {
    "status": "OK",
    "route": {
        "properties": {"totalDistance": 4025, "totalTime": 3914,
                       "landingUrl": "https://map.kakao.com/link/by/walk/test"},
        "legs": [{"steps": [{"properties": {
            "distance": 93, "time": 84, "guidance": "판교역 1번 출구로 이동",
        }, "path": {"points": [[127.1, 37.4]]}}]}],
    },
}
TRANSIT = {
    "status": "OK",
    "properties": {"landingURL": "https://map.kakao.com/link/by/publictraffic/test"},
    "routes": [{
        "properties": {"type": "BUS", "totalDistance": 5013, "totalTime": 2115,
                       "transfers": 0, "fare": {"value": 1350}},
        "steps": [{"properties": {
            "guidance": "76번 버스 탑승", "type": "BUS", "distance": 4127,
            "time": 1158, "stops": [{"name": "판교역동편"}],
            "vehicles": [{"name": "76", "type": "마을"}],
        }, "path": {"points": [[127.1, 37.4]]}}],
    }],
}


@pytest_asyncio.fixture
async def route_server(monkeypatch):
    """Replace all route endpoints with an isolated loopback HTTP server."""
    state = {"payload": deepcopy(WALK), "status": 200, "delay": 0}

    async def handler(request):
        state["path"] = request.path
        state["query"] = dict(request.query)
        state["authenticated"] = request.headers.get("Authorization") == "KakaoAK not-a-real-key"
        await asyncio.sleep(state["delay"])
        return web.json_response(state["payload"], status=state["status"])

    app = web.Application()
    app.router.add_get("/{mode}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setattr(api, "ROUTE_URLS", {
        mode: f"http://127.0.0.1:{port}/{mode}" for mode in api.ROUTE_URLS
    })
    async with aiohttp.ClientSession() as session:
        yield api.KakaoMapClient(session, "not-a-real-key"), state
    await runner.cleanup()


@pytest.mark.parametrize("mode", ["walk", "bicycle", "public_transport"])
async def test_route_parameters_and_summary(route_server, mode):
    client, state = route_server
    state["payload"] = deepcopy(TRANSIT if mode == "public_transport" else WALK)
    result = await client.async_get_route(**COORDINATES, mode=mode, start_name="출발역", end_name="도착역")
    assert state["path"] == f"/{mode}"
    assert state["authenticated"]
    assert state["query"] == {
        "start_x": "127.1111967", "start_y": "37.3947766",
        "end_x": "127.1262904", "end_y": "37.4199324",
        "s_name": "출발역", "e_name": "도착역", "input_coord": "WGS84", "output_coord": "WGS84",
    }
    assert result["count"] == 1
    route = result["routes"][0]
    assert route["duration_minutes"] == round(route["duration_s"] / 60, 1)
    assert "path" not in route["steps"][0]
    if mode == "public_transport":
        assert route["transfers"] == 0
        assert route["fare"] == {"value": 1350}
        assert route["steps"][0]["stops"] == ["판교역동편"]
        assert route["steps"][0]["vehicles"] == [{"name": "76", "type": "마을"}]
    else:
        assert route["fare"] is None and route["transfers"] is None


async def test_transit_alternatives_and_fare_range(route_server):
    client, state = route_server
    state["payload"] = deepcopy(TRANSIT)
    route = deepcopy(TRANSIT["routes"][0])
    route["properties"].update(type="SUBWAY", transfers=1, fare={"min": 1500, "max": 1800})
    state["payload"]["routes"].append(route)
    result = await client.async_get_route(**COORDINATES)
    assert result["count"] == 2
    assert result["routes"][1]["fare"] == {"min": 1500, "max": 1800}


@pytest.mark.parametrize("mode,status", [("public_transport", "NO_RESULTS"),
                                         ("walk", "ROUTE_RESULT_NOT_FOUND"),
                                         ("bicycle", "ROUTE_RESULT_NOT_FOUND")])
async def test_no_route_is_empty_success(route_server, mode, status):
    client, state = route_server
    state["payload"] = {"status": status}
    assert await client.async_get_route(**COORDINATES, mode=mode) == {
        "mode": mode, "count": 0, "routes": [], "route_url": "",
    }


@pytest.mark.parametrize("mode,status", [
    ("public_transport", "STARTNODES_NULL"), ("public_transport", "ENDNODES_NULL"),
    ("public_transport", "EQUAL_POINTS"), ("walk", "SAME_POINT"),
    ("walk", "START_LINK_NOT_FOUND"), ("walk", "END_LINK_NOT_FOUND"),
    ("walk", "TOO_MANY_SEARCH_LINK"), ("bicycle", "TOO_FAR_AWAY"),
])
async def test_route_failures_have_safe_messages(route_server, mode, status):
    client, state = route_server
    state["payload"] = {"status": status}
    with pytest.raises(api.KakaoMapRouteError) as raised:
        await client.async_get_route(**COORDINATES, mode=mode)
    assert str(raised.value)
    assert "not-a-real-key" not in str(raised.value)


@pytest.mark.parametrize("payload", [None, {}, {"status": 5}, {"status": "INVALID_REQUEST"},
                                      {"status": "UNEXPECTED"}, {"status": "OK", "route": {}},
                                      {"status": "OK", "route": []}])
async def test_malformed_route_rejected(route_server, payload):
    client, state = route_server
    state["payload"] = payload
    with pytest.raises(api.KakaoMapResponseError):
        await client.async_get_route(**COORDINATES, mode="walk")


@pytest.mark.parametrize("field,value", [("totalTime", -1), ("totalDistance", "100"),
                                        ("totalTime", True), ("landingUrl", [])])
async def test_invalid_summary_rejected(route_server, field, value):
    client, state = route_server
    state["payload"]["route"]["properties"][field] = value
    with pytest.raises(api.KakaoMapResponseError):
        await client.async_get_route(**COORDINATES, mode="walk")


@pytest.mark.parametrize("overrides", [
    {"start_latitude": float("nan")}, {"end_longitude": float("inf")},
    {"start_latitude": 91}, {"end_longitude": 181}, {"start_latitude": True},
    {"mode": "car"}, {"end_latitude": COORDINATES["start_latitude"],
                         "end_longitude": COORDINATES["start_longitude"]},
])
async def test_invalid_route_inputs_do_not_call_api(route_server, overrides):
    client, state = route_server
    with pytest.raises(ValueError):
        await client.async_get_route(**{**COORDINATES, **overrides})
    assert "query" not in state


@pytest.mark.parametrize("status,error", [
    (401, api.KakaoMapAuthError), (403, api.KakaoMapPermissionError),
    (429, api.KakaoMapRateLimitError), (503, api.KakaoMapConnectionError),
])
async def test_route_http_failures(route_server, status, error):
    client, state = route_server
    state["status"] = status
    with pytest.raises(error):
        await client.async_get_route(**COORDINATES, mode="walk")


async def test_route_action_http_response_and_cleanup(route_server, hass, entry, monkeypatch):
    client, state = route_server
    state["payload"] = deepcopy(TRANSIT)
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    assert hass.services.supports_response("kakaomap", "get_route") == SupportsResponse.ONLY
    result = await hass.services.async_call("kakaomap", "get_route", COORDINATES,
                                            blocking=True, return_response=True)
    assert result["routes"][0]["fare"]["value"] == 1350
    assert state["path"] == "/public_transport"
    await integration.async_unload_entry(hass, entry)
    assert not hass.services.has_service("kakaomap", "get_route")
    assert not hass.services.has_service("kakaomap", "search_places")


@pytest.mark.parametrize("data", [{}, {**COORDINATES, "mode": "car"},
                                  {**COORDINATES, "start_latitude": 91},
                                  {**COORDINATES, "start_latitude": float("nan")},
                                  {**COORDINATES, "end_latitude": COORDINATES["start_latitude"],
                                   "end_longitude": COORDINATES["start_longitude"]}])
async def test_ha_route_validation(hass, entry, monkeypatch, data):
    session = Mock()
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: session)
    await integration.async_setup_entry(hass, entry)
    with pytest.raises((vol.Invalid, ServiceValidationError)):
        await hass.services.async_call("kakaomap", "get_route", data, blocking=True, return_response=True)
    session.get.assert_not_called()


async def test_route_authentication_starts_reauth(route_server, hass, entry, monkeypatch):
    client, state = route_server
    state["status"] = 401
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    reauth = Mock()
    monkeypatch.setattr(type(entry), "async_start_reauth", reauth)
    await integration.async_setup_entry(hass, entry)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("kakaomap", "get_route", COORDINATES,
                                      blocking=True, return_response=True)
    reauth.assert_called_once_with(hass)
