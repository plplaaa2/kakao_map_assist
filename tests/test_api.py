"""Exercise HTTP and payload contracts; related files: api.py, const.py."""

import asyncio

import aiohttp
from aiohttp import web
import pytest
import pytest_asyncio

from custom_components.kakaomap import api
import custom_components.kakaomap as integration

PLACE = {
    "id": "123", "place_name": "테스트 장소", "address_name": "서울 강남구",
    "road_address_name": "서울 강남구 테스트로 1", "phone": "",
    "category_name": "테스트", "place_url": "https://place.map.kakao.com/123",
    "x": "127.01", "y": "37.51",
}


@pytest_asyncio.fixture
async def server(monkeypatch):
    """Serve controlled responses on loopback; never contact Kakao."""
    state = {"status": 200, "payload": {"meta": {"total_count": 1, "is_end": True},
                                         "documents": [PLACE]}, "delay": 0}

    async def handler(request):
        state["query"] = dict(request.query)
        state["authenticated"] = request.headers.get("Authorization") == "KakaoAK not-a-real-key"
        await asyncio.sleep(state["delay"])
        if "raw" in state:
            return web.Response(text=state["raw"], content_type="application/json")
        return web.json_response(state["payload"], status=state["status"])

    app = web.Application()
    app.router.add_get("/search", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setattr(api, "API_URL", f"http://127.0.0.1:{port}/search")
    async with aiohttp.ClientSession() as session:
        yield api.KakaoMapClient(session, "not-a-real-key"), state
    await runner.cleanup()


async def test_search_returns_places_and_numeric_coordinates(server):
    client, state = server
    result = await client.async_search(name="  카페 ", address=" 서울 강남구 ", limit=3)
    assert state["query"] == {"query": "서울 강남구 카페", "size": "3", "rect": api.SEARCH_RECT}
    assert state["authenticated"]
    assert result["places"][0]["latitude"] == 37.51
    assert result["places"][0]["longitude"] == 127.01
    assert result["count"] == 1
    assert "x" not in result["places"][0]


async def test_empty_results_are_successful(server):
    client, state = server
    state["payload"] = {"meta": {"total_count": 0, "is_end": True}, "documents": []}
    assert (await client.async_search(address="없는장소"))["places"] == []


async def test_http_result_through_real_ha_action(server, hass, entry, monkeypatch):
    """Exercise the HA registry, client HTTP request, and response together."""
    client, state = server
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    response = await hass.services.async_call(
        "kakaomap", "search_places", {"address": "서울", "name": "테스트 장소"},
        blocking=True, return_response=True,
    )
    assert response["query"] == "서울 테스트 장소"
    assert response["places"][0]["latitude"] == 37.51
    assert state["authenticated"]
    await integration.async_unload_entry(hass, entry)


@pytest.mark.parametrize("status,error", [
    (401, api.KakaoMapAuthError), (403, api.KakaoMapPermissionError),
    (429, api.KakaoMapRateLimitError), (500, api.KakaoMapConnectionError),
    (400, api.KakaoMapResponseError), (302, api.KakaoMapResponseError),
])
async def test_http_failures_are_safe(server, status, error):
    client, state = server
    state["status"] = status
    with pytest.raises(error) as raised:
        await client.async_search(name="서울역")
    assert "not-a-real-key" not in str(raised.value)


@pytest.mark.parametrize("payload", [None, {}, {"documents": {}, "meta": {}},
    {"documents": [{**PLACE, "x": "NaN"}], "meta": {"total_count": 1, "is_end": True}},
    {"documents": [PLACE], "meta": {"total_count": "1", "is_end": True}},
])
async def test_malformed_payload(server, payload):
    client, state = server
    state["payload"] = payload
    with pytest.raises(api.KakaoMapResponseError):
        await client.async_search(name="서울역")


async def test_invalid_json(server):
    client, state = server
    state["raw"] = "not json"
    with pytest.raises(api.KakaoMapResponseError):
        await client.async_search(name="서울역")


async def test_timeout(server, monkeypatch):
    client, state = server
    state["delay"] = 0.05
    monkeypatch.setattr(api, "REQUEST_TIMEOUT", 0.01)
    with pytest.raises(api.KakaoMapConnectionError):
        await client.async_search(name="서울역")


@pytest.mark.parametrize("inputs", [{}, {"name": "  "}, {"name": "서울역", "limit": 0},
                                      {"name": "서울역", "limit": 16}])
async def test_invalid_input_does_not_send_request(server, inputs):
    client, state = server
    with pytest.raises(ValueError):
        await client.async_search(**inputs)
    assert "query" not in state
