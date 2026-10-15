"""Verify elapsed-time ETA, ordered stops and comparisons; related files: api.py, routes.py."""

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import Mock
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import probatio as vol
import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import llm

import custom_components.kakaomap as integration
from custom_components.kakaomap import api
from tests.test_car_routes import CAR
from tests.test_llm import context
from tests.test_routes import COORDINATES, TRANSIT, WALK, route_server  # noqa: F401

STOPS = [{"latitude": 37.4, "longitude": 127.12, "name": "주유소/1,2"},
         {"latitude": 37.41, "longitude": 127.13, "name": "약국"}]


@pytest.mark.parametrize("mode,payload", [("car", CAR), ("walk", WALK),
                                          ("bicycle", WALK), ("public_transport", TRANSIT)])
async def test_eta_all_modes_midnight_and_before_http(route_server, monkeypatch, mode, payload):
    client, state = route_server
    client._time_zone = ZoneInfo("Asia/Seoul")
    state["payload"] = deepcopy(payload)
    started = datetime(2026, 10, 15, 14, 50, tzinfo=UTC)
    clock = Mock(wraps=datetime)
    clock.now.return_value = started
    monkeypatch.setattr(api, "datetime", clock)
    original = client._async_request

    async def delayed_clock(*args):
        # HTTP completes later, but the elapsed-time estimate must use request start.
        clock.now.return_value = datetime(2026, 10, 15, 15, 0, tzinfo=UTC)
        return await original(*args)

    monkeypatch.setattr(client, "_async_request", delayed_clock)
    result = await client.async_get_route(**COORDINATES, mode=mode)
    departure = datetime.fromisoformat(result["departure_time"])
    assert result["time_zone"] == "Asia/Seoul"
    assert result["departure_time"] == "2026-10-15T23:50:00+09:00"
    for route in result["routes"]:
        arrival = datetime.fromisoformat(route["arrival_time"])
        assert arrival.day == 16
        assert (arrival - departure).total_seconds() == route["duration_s"]


async def test_eta_dst_elapsed_seconds(route_server, monkeypatch):
    client, state = route_server
    client._time_zone = ZoneInfo("America/New_York")
    state["payload"] = deepcopy(CAR)
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2026, 11, 1, 5, 50, tzinfo=UTC)
    monkeypatch.setattr(api, "datetime", clock)
    result = await client.async_get_route(**COORDINATES, mode="car")
    assert result["departure_time"] == "2026-11-01T01:50:00-04:00"
    assert result["routes"][0]["arrival_time"] == "2026-11-01T01:20:00-05:00"


async def test_ordered_waypoints_request_link_and_no_mutation(route_server):
    client, state = route_server
    state["payload"] = deepcopy(CAR)
    stops = deepcopy(STOPS)
    result = await client.async_get_route(**COORDINATES, mode="car", waypoints=stops)
    assert state["query"]["waypoints"] == "127.12,37.4|127.13,37.41"
    assert stops == STOPS and result["waypoints"] == STOPS
    segments = result["route_url"].split("/")[6:]
    assert len(segments) == 4
    assert unquote(segments[1]).startswith("주유소/1,2,37.4,127.12")
    assert unquote(segments[2]).startswith("약국,37.41,127.13")
    assert result["routes"][0]["route_url"] == result["route_url"]


async def test_five_waypoints_and_default_names(route_server):
    client, state = route_server
    state["payload"] = deepcopy(CAR)
    result = await client.async_get_route(**COORDINATES, mode="car", waypoints=[
        {"latitude": 37.4 + index / 100, "longitude": 127.12} for index in range(5)
    ])
    assert len(state["query"]["waypoints"].split("|")) == 5
    assert result["waypoints"][-1]["name"] == "경유지 5"


@pytest.mark.parametrize("options", [
    {"waypoints": [STOPS[0]] * 6}, {"waypoints": "place"}, {"waypoints": [None]},
    {"waypoints": [{}]}, {"waypoints": [{"latitude": True, "longitude": 127.0}]},
    {"waypoints": [{"latitude": float("nan"), "longitude": 127.0}]},
    {"waypoints": [{"latitude": 37.0, "longitude": 181}]},
    {"waypoints": [{**STOPS[0], "name": None}]},
    {"waypoints": [{**STOPS[0], "unexpected": 1}]}, {"alternatives": "true"},
    {"alternatives": 1}, {"mode": "public_transport", "waypoints": STOPS},
    {"mode": "walk", "alternatives": True}, {"mode": "bicycle", "waypoints": STOPS},
])
async def test_extension_validation_before_http(route_server, options):
    client, state = route_server
    with pytest.raises(ValueError):
        await client.async_get_route(**{**COORDINATES, "mode": "car", **options})
    assert "query" not in state


async def test_alternatives_compare_same_conditions_without_sorting(route_server):
    client, state = route_server
    primary = deepcopy(CAR["routes"][0])
    faster = deepcopy(primary)
    faster["summary"].update(duration=1500, distance=15000, fare={"toll": 2000})
    cheaper = deepcopy(primary)
    cheaper["summary"].update(duration=2100, distance=12000, fare={"toll": 0})
    state["payload"] = {"routes": [primary, faster, cheaper]}
    result = await client.async_get_route(**COORDINATES, mode="car", waypoints=STOPS,
                                           alternatives=True, avoid=["ferries"])
    assert state["query"]["alternatives"] == "true"
    assert state["query"]["avoid"] == "ferries" and state["query"]["priority"] == "RECOMMEND"
    assert result["count"] == 3 and result["alternatives_requested"]
    assert [route["route_index"] for route in result["routes"]] == [1, 2, 3]
    assert [route["is_primary"] for route in result["routes"]] == [True, False, False]
    assert result["routes"][1]["difference_from_primary"] == {
        "duration_s": -300, "distance_m": 2655, "toll_fare": 800,
    }
    assert result["routes"][2]["difference_from_primary"]["toll_fare"] == -1200
    assert result["routes"][1]["arrival_time"] < result["routes"][0]["arrival_time"]


async def test_failed_alternative_keeps_primary_and_indices(route_server):
    client, state = route_server
    state["payload"] = {"routes": [deepcopy(CAR["routes"][0]), {"result_code": 1},
                                    deepcopy(CAR["routes"][0])]}
    result = await client.async_get_route(**COORDINATES, mode="car", alternatives=True)
    assert result["count"] == 2 and result["skipped_alternatives"] == 1
    assert [route["route_index"] for route in result["routes"]] == [1, 3]


async def test_single_candidate_no_fabricated_alternative(route_server):
    client, state = route_server
    state["payload"] = deepcopy(CAR)
    result = await client.async_get_route(**COORDINATES, mode="car", alternatives=True)
    assert result["count"] == 1 and len(result["routes"]) == 1
    assert result["routes"][0]["is_primary"]


async def test_assist_extensions_use_ha_timezone(route_server, hass, entry, monkeypatch):
    client, state = route_server
    state["payload"] = deepcopy(CAR)
    monkeypatch.setattr(hass.config, "time_zone", "Asia/Seoul")
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    instance = await llm.async_get_api(hass, f"kakaomap-{entry.entry_id}", context())
    result = await instance.async_call_tool(llm.ToolInput(tool_name="kakaomap__get_route", tool_args={
        **COORDINATES, "mode": "car", "waypoints": STOPS, "alternatives": True,
    }))
    assert result.data["time_zone"] == "Asia/Seoul"
    assert result.data["routes"][0]["arrival_time"].endswith("+09:00")
    assert state["query"]["alternatives"] == "true"
    assert state["query"]["waypoints"] == "127.12,37.4|127.13,37.41"
    assert "stopover/dwell time is excluded" in instance.api_prompt
    assert "Only on a request for other routes or comparison" in instance.api_prompt


@pytest.mark.parametrize("options", [{"waypoints": STOPS * 3},
    {"waypoints": [{"latitude": 37.5}]}, {"alternatives": "true"},
    {"mode": "walk", "waypoints": STOPS}, {"mode": "public_transport", "alternatives": True}])
async def test_action_validation_no_http(route_server, hass, entry, monkeypatch, options):
    client, state = route_server
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: client._session)
    await integration.async_setup_entry(hass, entry)
    with pytest.raises((vol.Invalid, ServiceValidationError)):
        await hass.services.async_call("kakaomap", "get_route",
            {**COORDINATES, "mode": "car", **options}, blocking=True, return_response=True)
    assert "query" not in state
