"""Verify nearby HTTP, HA actions and Assist; related files: api.py, llm.py."""

from unittest.mock import Mock

import aiohttp
from aiohttp import web
import pytest
import pytest_asyncio
import probatio as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import llm

import custom_components.kakaomap as integration
from custom_components.kakaomap import api
from custom_components.kakaomap.const import CATEGORY_CODES
from tests.test_api import PLACE
from tests.test_llm import context

CENTER = {"latitude": 37.5, "longitude": 127.0}


@pytest_asyncio.fixture
async def nearby_server(monkeypatch):
    """Intercept both official endpoint types on loopback with fake credentials."""
    state = {"calls": 0, "status": 200, "payload": {
        "meta": {"total_count": 2, "is_end": True},
        "documents": [{**PLACE, "distance": "800"},
                      {**PLACE, "id": "456", "distance": "100"}],
    }}

    async def handler(request):
        state.update(calls=state["calls"] + 1, path=request.path, params=dict(request.query))
        return web.json_response(state["payload"], status=state["status"])

    app = web.Application()
    app.router.add_get("/{kind}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setattr(api, "API_URL", f"http://127.0.0.1:{port}/keyword")
    monkeypatch.setattr(api, "CATEGORY_URL", f"http://127.0.0.1:{port}/category")
    try:
        async with aiohttp.ClientSession() as session:
            yield api.KakaoMapClient(session, "not-a-real-key"), state
    finally:
        await runner.cleanup()


@pytest.mark.parametrize("search,path", [({"query": " 스타벅스 "}, "/keyword"),
                                         ({"category": "PM9"}, "/category")])
async def test_http_scope_distance_and_order(nearby_server, search, path):
    client, state = nearby_server
    result = await client.async_search_nearby(**CENTER, **search)
    assert state["path"] == path
    assert state["params"] == {
        "x": "127.0", "y": "37.5", "radius": "1000", "size": "5", "sort": "distance",
        ("query" if path == "/keyword" else "category_group_code"):
        ("스타벅스" if path == "/keyword" else "PM9"),
    }
    assert result["center"] == CENTER and result["radius_m"] == 1000
    assert [place["distance_m"] for place in result["places"]] == [100, 800]
    assert result["count"] == result["total_count"] == 2
    assert result["places"][0]["latitude"] == 37.51


@pytest.mark.parametrize("category", CATEGORY_CODES)
async def test_official_categories(nearby_server, category):
    client, state = nearby_server
    await client.async_search_nearby(**CENTER, category=category, radius=20000, limit=15)
    assert state["params"]["category_group_code"] == category
    assert state["params"]["radius"] == "20000" and state["params"]["size"] == "15"


@pytest.mark.parametrize("overrides", [
    {"query": ""}, {"query": "  "}, {"category": "PM9"}, {"category": "invalid"},
    {"latitude": float("nan")}, {"longitude": float("inf")}, {"latitude": 91},
    {"longitude": -181}, {"latitude": True}, {"radius": 0}, {"radius": 20001},
    {"radius": 1.5}, {"radius": True}, {"limit": 0}, {"limit": 16}, {"limit": True},
    {"query": None},
])
async def test_invalid_input_never_requests(nearby_server, overrides):
    client, state = nearby_server
    args = {**CENTER, "query": "약국", **overrides}
    with pytest.raises(ValueError):
        await client.async_search_nearby(**args)
    assert state["calls"] == 0


@pytest.mark.parametrize("distance", [None, "", "NaN", "-1", "1.5", "1001", 100, True])
async def test_bad_distance_is_response_error(nearby_server, distance):
    client, state = nearby_server
    state["payload"]["documents"][0]["distance"] = distance
    with pytest.raises(api.KakaoMapResponseError):
        await client.async_search_nearby(**CENTER, query="약국")


async def test_empty_result(nearby_server):
    client, state = nearby_server
    state["payload"] = {"meta": {"total_count": 0, "is_end": True}, "documents": []}
    result = await client.async_search_nearby(**CENTER, category="PM9")
    assert result["count"] == 0 and result["places"] == []


async def test_assist_action_http_and_unload(nearby_server, hass, entry, monkeypatch):
    client, state = nearby_server
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    instance = await llm.async_get_api(hass, f"kakaomap-{entry.entry_id}", context())
    response = await instance.async_call_tool(llm.ToolInput(
        tool_name="kakaomap__search_nearby", tool_args={**CENTER, "category": "PM9"},
    ))
    assert response.data["places"][0]["distance_m"] == 100
    assert state["params"]["radius"] == "1000"
    assert "not walking distances" in instance.api_prompt
    await integration.async_unload_entry(hass, entry)
    assert not hass.services.has_service("kakaomap", "search_nearby")


@pytest.mark.parametrize("status,message", [(401, "인증"), (403, "권한"),
                                            (429, "한도"), (500, "연결"), (400, "거부")])
async def test_action_errors_and_auth_notification(nearby_server, hass, entry, monkeypatch, status, message):
    client, state = nearby_server
    state["status"] = status
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    # Both HA callbacks are synchronous; record them without scheduling coroutines.
    notify, reauth = Mock(), Mock()
    monkeypatch.setattr(integration, "async_notify_auth_failure", notify)
    monkeypatch.setattr(type(entry), "async_start_reauth", reauth)
    await integration.async_setup_entry(hass, entry)
    instance = await llm.async_get_api(hass, f"kakaomap-{entry.entry_id}", context())
    with pytest.raises(HomeAssistantError, match=message):
        await instance.async_call_tool(llm.ToolInput(
            tool_name="kakaomap__search_nearby", tool_args={**CENTER, "category": "PM9"},
        ))
    assert notify.call_count == reauth.call_count == (1 if status == 401 else 0)


@pytest.mark.parametrize("args", [{}, {**CENTER}, {**CENTER, "query": "약국", "category": "PM9"},
                                  {**CENTER, "query": "약국", "radius": 20001}])
async def test_action_validation_before_http(nearby_server, hass, entry, monkeypatch, args):
    client, state = nearby_server
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    with pytest.raises((ServiceValidationError, vol.Invalid)):
        await hass.services.async_call("kakaomap", "search_nearby", args,
                                       blocking=True, return_response=True)
    assert state["calls"] == 0
