"""Verify Mobility driving contracts; related files: api.py, routes.py, llm.py."""

import json
from copy import deepcopy
from unittest.mock import Mock
from urllib.parse import unquote

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

import custom_components.kakaomap as integration
from custom_components.kakaomap import api
from tests.test_llm import context
from tests.test_routes import COORDINATES, route_server  # noqa: F401

CAR = {"routes": [{
    "result_code": 0,
    "summary": {"distance": 12345, "duration": 1800, "priority": "RECOMMEND",
                "fare": {"toll": 1200, "taxi": 22200}},
    "sections": [{"roads": [{"vertexes": [127.0, 37.0]}], "guides": [
        {"guidance": "판교로 방면 우회전", "distance": 100, "duration": 20,
         "x": 127.0, "y": 37.0},
    ]}],
}]}


async def test_car_defaults_and_summary(route_server):
    client, state = route_server
    state["payload"] = deepcopy(CAR)
    result = await client.async_get_route(**COORDINATES, mode="car", start_name="출발/역,1")
    assert state["path"] == "/car" and state["authenticated"]
    assert state["query"] == {
        "origin": "127.1111967,37.3947766", "destination": "127.1262904,37.4199324",
        "priority": "RECOMMEND", "summary": "false", "alternatives": "false",
    }
    assert result["priority"] == "RECOMMEND" and result["avoid"] == []
    route = result["routes"][0]
    assert route["duration_minutes"] == 30 and route["distance_m"] == 12345
    assert route["toll_fare"] == 1200 and route["fare"] is None
    assert route["transfers"] is None
    assert route["steps"] == [{"guidance": "판교로 방면 우회전", "distance_m": 100,
                               "duration_s": 20, "mode": "car"}]
    assert "vertexes" not in json.dumps(result) and "taxi" not in json.dumps(result)
    assert "/car/%" in result["route_url"] and "%2F" in result["route_url"]
    assert "/출발/역,1,37.3947766,127.1111967/" in unquote(result["route_url"])


@pytest.mark.parametrize("priority,avoid", [("TIME", []), ("DISTANCE", ["toll"]),
    ("RECOMMEND", ["motorway", "ferries", "schoolzone", "uturn", "toll", "toll"])])
async def test_explicit_preferences(route_server, priority, avoid):
    client, state = route_server
    state["payload"] = deepcopy(CAR)
    state["payload"]["routes"][0]["summary"]["priority"] = priority
    result = await client.async_get_route(**COORDINATES, mode="car", priority=priority, avoid=avoid)
    assert state["query"]["priority"] == priority
    assert state["query"].get("avoid", "") == "|".join(dict.fromkeys(avoid))
    assert result["routes"][0]["priority"] == priority


@pytest.mark.parametrize("options", [{"priority": "BIG_ROAD"}, {"avoid": ["invalid"]},
    {"avoid": "toll"}, {"mode": "walk", "priority": "TIME"},
    {"mode": "public_transport", "avoid": ["toll"]}])
async def test_invalid_preferences_no_http(route_server, options):
    client, state = route_server
    with pytest.raises(ValueError):
        await client.async_get_route(**{**COORDINATES, "mode": "car", **options})
    assert "query" not in state


@pytest.mark.parametrize("code", [1, 102, 103, 104, 999])
async def test_car_route_failure_safe(route_server, code):
    client, state = route_server
    state["payload"] = {"routes": [{"result_code": code, "result_msg": "untrusted upstream"}]}
    with pytest.raises(api.KakaoMapRouteError, match="자동차 경로") as raised:
        await client.async_get_route(**COORDINATES, mode="car")
    assert "untrusted" not in str(raised.value)


@pytest.mark.parametrize("payload", [None, {}, {"routes": []}, {"routes": [{}]},
    {"routes": [{"result_code": True}]}, {"routes": [{"result_code": 0, "summary": {}}]}])
async def test_malformed_car_response(route_server, payload):
    client, state = route_server
    state["payload"] = payload
    with pytest.raises(api.KakaoMapResponseError):
        await client.async_get_route(**COORDINATES, mode="car")


@pytest.mark.parametrize("field,value", [("duration", -1), ("distance", True),
    ("priority", "UNKNOWN"), ("fare", {"toll": -1}), ("fare", {"taxi": 1200})])
async def test_invalid_car_summary(route_server, field, value):
    client, state = route_server
    state["payload"] = deepcopy(CAR)
    state["payload"]["routes"][0]["summary"][field] = value
    with pytest.raises(api.KakaoMapResponseError):
        await client.async_get_route(**COORDINATES, mode="car")


async def test_car_assist_http_preferences(route_server, hass, entry, monkeypatch):
    client, state = route_server
    state["payload"] = deepcopy(CAR)
    state["payload"]["routes"][0]["summary"].update(priority="TIME", fare={"toll": 0})
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    instance = await llm.async_get_api(hass, f"kakaomap-{entry.entry_id}", context())
    result = await instance.async_call_tool(llm.ToolInput(tool_name="kakaomap__get_route", tool_args={
        **COORDINATES, "mode": "car", "priority": "TIME", "avoid": ["toll"],
    }))
    assert result.data["routes"][0]["toll_fare"] == 0
    assert state["query"]["avoid"] == "toll" and state["query"]["priority"] == "TIME"
    assert "default priority to RECOMMEND" in instance.api_prompt
    assert "Only on explicit request" in instance.api_prompt


@pytest.mark.parametrize("status,message", [(401, "인증"), (403, "권한"),
                                            (429, "한도"), (500, "연결")])
async def test_car_action_http_errors(route_server, hass, entry, monkeypatch, status, message):
    client, state = route_server
    state["status"] = status
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    notify, reauth = Mock(), Mock()
    monkeypatch.setattr(integration, "async_notify_auth_failure", notify)
    monkeypatch.setattr(type(entry), "async_start_reauth", reauth)
    await integration.async_setup_entry(hass, entry)
    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call("kakaomap", "get_route", {**COORDINATES, "mode": "car"},
                                       blocking=True, return_response=True)
    assert notify.call_count == reauth.call_count == (1 if status == 401 else 0)
