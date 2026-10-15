"""Verify conversation-user isolation and home/away resolution; related file: llm.py."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import llm

from tests.test_llm import setup_provider


async def user_api(hass, entry, monkeypatch, user_id="caller"):
    """Create a real registered API instance with a request-scoped identity."""
    instance = await setup_provider(hass, entry, monkeypatch)
    instance.llm_context.context = Context(user_id=user_id)
    return instance


async def locate(instance, args=None):
    return await instance.async_call_tool(llm.ToolInput(
        tool_name="kakaomap__get_current_location", tool_args=args or {},
    ))


async def test_home_uses_config_not_gps(hass, entry, monkeypatch):
    instance = await user_api(hass, entry, monkeypatch)
    hass.config.latitude, hass.config.longitude = 37.5, 127.0
    hass.states.async_set("person.caller", "home", {
        "user_id": "caller", "latitude": 38.0, "longitude": 128.0,
    })
    result = (await locate(instance)).data
    assert result["latitude"] == 37.5 and result["longitude"] == 127.0
    assert result["at_home"] and result["source"] == "home" and result["name"] == "집"
    assert result["state_last_updated"] == hass.states.get("person.caller").last_updated.isoformat()
    assert "user_id" not in result and "entity_id" not in result


async def test_home_without_gps_and_fresh_config(hass, entry, monkeypatch):
    instance = await user_api(hass, entry, monkeypatch)
    hass.states.async_set("person.caller", "home", {"user_id": "caller"})
    hass.config.latitude, hass.config.longitude = 37.5, 127.0
    assert (await locate(instance)).data["latitude"] == 37.5
    hass.config.latitude = 37.6
    assert (await locate(instance)).data["latitude"] == 37.6


@pytest.mark.parametrize("state", ["not_home", "회사"])
async def test_away_uses_own_person_and_connects_tools(hass, entry, monkeypatch, state):
    instance = await user_api(hass, entry, monkeypatch)
    hass.states.async_set("person.other", "home", {"user_id": "other", "latitude": 1, "longitude": 2})
    hass.states.async_set("person.caller", state, {
        "user_id": "caller", "latitude": 37.6, "longitude": 127.1,
    })
    result = (await locate(instance)).data
    assert result["latitude"] == 37.6 and result["longitude"] == 127.1
    assert result["source"] == "person" and not result["at_home"]
    entry.runtime_data.async_search_nearby = AsyncMock(return_value={"places": []})
    entry.runtime_data.async_get_route = AsyncMock(return_value={"routes": []})
    await instance.async_call_tool(llm.ToolInput(tool_name="kakaomap__search_nearby", tool_args={
        "latitude": result["latitude"], "longitude": result["longitude"], "category": "PM9",
    }))
    await instance.async_call_tool(llm.ToolInput(tool_name="kakaomap__get_route", tool_args={
        "start_latitude": result["latitude"], "start_longitude": result["longitude"],
        "end_latitude": 37.5, "end_longitude": 127.0,
    }))
    assert entry.runtime_data.async_search_nearby.call_args.kwargs["latitude"] == 37.6
    assert entry.runtime_data.async_get_route.call_args.kwargs["start_longitude"] == 127.1


@pytest.mark.parametrize("user_id", [None, "unlinked"])
async def test_missing_identity_never_uses_other_or_home(hass, entry, monkeypatch, user_id):
    instance = await user_api(hass, entry, monkeypatch, user_id)
    hass.states.async_set("person.other", "home", {"user_id": "other"})
    with pytest.raises(HomeAssistantError, match="기준 위치"):
        await locate(instance)


async def test_ambiguous_person_fails(hass, entry, monkeypatch):
    instance = await user_api(hass, entry, monkeypatch)
    for entity in ("person.one", "person.two"):
        hass.states.async_set(entity, "home", {"user_id": "caller"})
    with pytest.raises(HomeAssistantError, match="기준 위치"):
        await locate(instance)


@pytest.mark.parametrize("state,attributes", [
    ("unknown", {}), ("unavailable", {}), ("not_home", {}),
    ("not_home", {"latitude": float("nan"), "longitude": 127.0}),
    ("not_home", {"latitude": 37.5, "longitude": float("inf")}),
    ("not_home", {"latitude": True, "longitude": 127.0}),
    ("not_home", {"latitude": 91, "longitude": 127.0}),
])
async def test_unusable_location_requests_reference(hass, entry, monkeypatch, state, attributes):
    instance = await user_api(hass, entry, monkeypatch)
    hass.states.async_set("person.caller", state, {"user_id": "caller", **attributes})
    with pytest.raises(HomeAssistantError, match="기준 위치"):
        await locate(instance)


async def test_cannot_supply_another_person(hass, entry, monkeypatch):
    instance = await user_api(hass, entry, monkeypatch)
    with pytest.raises(ServiceValidationError):
        await locate(instance, {"user_id": "other", "entity_id": "person.other"})


async def test_same_provider_isolates_requests(hass, entry, monkeypatch):
    instance = await user_api(hass, entry, monkeypatch)
    hass.states.async_set("person.caller", "not_home", {
        "user_id": "caller", "latitude": 37.6, "longitude": 127.1,
    })
    hass.states.async_set("person.other", "not_home", {
        "user_id": "other", "latitude": 37.7, "longitude": 127.2,
    })
    assert (await locate(instance)).data["latitude"] == 37.6
    other = await llm.async_get_api(hass, f"kakaomap-{entry.entry_id}", llm.LLMContext(
        platform="test_agent", context=Context(user_id="other"), language="ko",
        assistant="conversation", device_id=None,
    ))
    assert (await locate(other)).data["latitude"] == 37.7
    assert (await locate(instance)).data["latitude"] == 37.6
