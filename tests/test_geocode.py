"""Verify address geocoding and action composition; related files: api.py, llm.py."""

from copy import deepcopy
from unittest.mock import AsyncMock, Mock

import aiohttp
from aiohttp import web
import probatio as vol
import pytest
import pytest_asyncio
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import llm

import custom_components.kakaomap as integration
from custom_components.kakaomap import api
from tests.test_llm import context

ADDRESS = {
    "address_name": "서울 중구 세종대로 110", "address_type": "ROAD_ADDR",
    "x": "126.978", "y": "37.5665",
    "address": {"address_name": "서울 중구 태평로1가 31"},
    "road_address": {"address_name": "서울 중구 세종대로 110", "zone_no": "04524"},
}


@pytest_asyncio.fixture
async def address_server(monkeypatch):
    """Use loopback only, never a live Kakao endpoint."""
    state = {"calls": 0, "status": 200, "payload": {
        "meta": {"total_count": 1, "is_end": True}, "documents": [deepcopy(ADDRESS)],
    }}

    async def handler(request):
        state.update(calls=state["calls"] + 1, params=dict(request.query))
        return web.json_response(state["payload"], status=state["status"])

    app = web.Application()
    app.router.add_get("/address", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setattr(api, "ADDRESS_URL", f"http://127.0.0.1:{port}/address")
    try:
        async with aiohttp.ClientSession() as session:
            yield api.KakaoMapClient(session, "not-a-real-key"), state
    finally:
        await runner.cleanup()


@pytest.mark.parametrize("query", ["서울 중구 세종대로 110", "서울 중구 태평로1가 31"])
async def test_road_and_lot_queries(address_server, query):
    client, state = address_server
    result = await client.async_geocode_address(query=f" {query} ")
    assert state["params"] == {"query": query, "size": "5"}
    assert result["query"] == query and result["count"] == 1
    assert result["addresses"][0] == {
        "address_name": ADDRESS["address_name"], "address_type": "ROAD_ADDR",
        "latitude": 37.5665, "longitude": 126.978,
        "jibun_address": "서울 중구 태평로1가 31",
        "road_address": "서울 중구 세종대로 110", "zone_no": "04524",
    }


@pytest.mark.parametrize("missing", ["address", "road_address"])
async def test_optional_address_missing(address_server, missing):
    client, state = address_server
    state["payload"]["documents"][0][missing] = None
    result = (await client.async_geocode_address(query="주소"))["addresses"][0]
    assert result["jibun_address" if missing == "address" else "road_address"] is None
    if missing == "road_address":
        assert result["zone_no"] is None


async def test_multiple_candidates_and_empty(address_server):
    client, state = address_server
    state["payload"]["documents"].append({**ADDRESS, "address_name": "다른 후보"})
    state["payload"]["meta"]["total_count"] = 2
    result = await client.async_geocode_address(query="주소", limit=1)
    assert result["count"] == 1 and result["total_count"] == 2
    assert state["params"]["size"] == "1"
    assert (await client.async_geocode_address(query="주소"))["count"] == 2
    state["payload"] = {"documents": [], "meta": {"total_count": 0, "is_end": True}}
    assert (await client.async_geocode_address(query="주소"))["addresses"] == []


@pytest.mark.parametrize("args", [{"query": ""}, {"query": "  "}, {"query": None},
    {"query": "주소", "limit": 0}, {"query": "주소", "limit": 16},
    {"query": "주소", "limit": True}])
async def test_invalid_input_no_http(address_server, args):
    client, state = address_server
    with pytest.raises(ValueError):
        await client.async_geocode_address(**args)
    assert state["calls"] == 0


@pytest.mark.parametrize("patch", [
    {"x": "NaN"}, {"y": "91"}, {"address_type": "invalid"},
    {"address_name": []}, {"address": []}, {"road_address": {}},
    {"road_address": {"address_name": "주소", "zone_no": 123}},
])
async def test_bad_address_is_safe_error(address_server, patch):
    client, state = address_server
    state["payload"]["documents"][0].update(patch)
    with pytest.raises(api.KakaoMapResponseError):
        await client.async_geocode_address(query="주소")


@pytest.mark.parametrize("payload", [None, {}, {"documents": {}, "meta": {}},
    {"documents": [], "meta": {"total_count": -1, "is_end": True}}])
async def test_malformed_payload(address_server, payload):
    client, state = address_server
    state["payload"] = payload
    with pytest.raises(api.KakaoMapResponseError):
        await client.async_geocode_address(query="주소")


async def test_assist_address_to_nearby_and_route(address_server, hass, entry, monkeypatch):
    client, state = address_server
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    instance = await llm.async_get_api(hass, f"kakaomap-{entry.entry_id}", context())
    response = await instance.async_call_tool(llm.ToolInput(
        tool_name="kakaomap__geocode_address", tool_args={"query": ADDRESS["address_name"]},
    ))
    address = response.data["addresses"][0]
    entry.runtime_data.async_search_nearby = AsyncMock(return_value={"places": []})
    entry.runtime_data.async_get_route = AsyncMock(return_value={"routes": []})
    await instance.async_call_tool(llm.ToolInput(tool_name="kakaomap__search_nearby", tool_args={
        "latitude": address["latitude"], "longitude": address["longitude"], "category": "PM9",
    }))
    await instance.async_call_tool(llm.ToolInput(tool_name="kakaomap__get_route", tool_args={
        "start_latitude": 37.5, "start_longitude": 127.0,
        "end_latitude": address["latitude"], "end_longitude": address["longitude"],
    }))
    assert entry.runtime_data.async_search_nearby.call_args.kwargs["latitude"] == 37.5665
    assert entry.runtime_data.async_get_route.call_args.kwargs["end_longitude"] == 126.978
    assert "Default to keyword place search" in instance.api_prompt
    assert "road-name or lot-number address" in instance.api_prompt
    assert "ask the user to choose the correct address" in instance.api_prompt
    await integration.async_unload_entry(hass, entry)
    assert not hass.services.has_service("kakaomap", "geocode_address")


@pytest.mark.parametrize("status,message", [(401, "인증"), (403, "권한"),
                                            (429, "한도"), (500, "연결"), (400, "거부")])
async def test_assist_http_errors(address_server, hass, entry, monkeypatch, status, message):
    client, state = address_server
    state["status"] = status
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    notify, reauth = Mock(), Mock()
    monkeypatch.setattr(integration, "async_notify_auth_failure", notify)
    monkeypatch.setattr(type(entry), "async_start_reauth", reauth)
    await integration.async_setup_entry(hass, entry)
    instance = await llm.async_get_api(hass, f"kakaomap-{entry.entry_id}", context())
    with pytest.raises(HomeAssistantError, match=message):
        await instance.async_call_tool(llm.ToolInput(
            tool_name="kakaomap__geocode_address", tool_args={"query": "주소"},
        ))
    assert notify.call_count == reauth.call_count == (1 if status == 401 else 0)


@pytest.mark.parametrize("args", [{}, {"query": " "}, {"query": "주소", "limit": 16}])
async def test_action_input_errors(address_server, hass, entry, monkeypatch, args):
    client, state = address_server
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    with pytest.raises((ServiceValidationError, vol.Invalid)):
        await hass.services.async_call("kakaomap", "geocode_address", args,
                                       blocking=True, return_response=True)
    assert state["calls"] == 0
