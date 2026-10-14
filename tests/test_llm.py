"""Exercise registered Assist APIs; related files: llm.py, __init__.py, manifest.json."""

from unittest.mock import AsyncMock, Mock

import probatio
import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import llm

import custom_components.kakaomap as integration
from custom_components.kakaomap.llm import async_get_tools


def context():
    """Use a conversation context without any real account credentials."""
    return llm.LLMContext(platform="test_agent", context=Context(), language="ko",
                          assistant="conversation", device_id=None)


async def setup_provider(hass, entry, monkeypatch):
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: Mock())
    await integration.async_setup_entry(hass, entry)
    return await llm.async_get_api(hass, f"kakaomap-{entry.entry_id}", context())


async def test_provider_list_tools_and_schemas(hass, entry, monkeypatch):
    instance = await setup_provider(hass, entry, monkeypatch)
    assert [(api.id, api.name) for api in llm.async_get_apis(hass)] == [
        (f"kakaomap-{entry.entry_id}", "KakaoMap")
    ]
    assert {tool.name for tool in instance.tools} == {
        "kakaomap__search_places", "kakaomap__get_route", "kakaomap__get_home_location"
    }
    for tool in instance.tools:
        assert tool.integration == "kakaomap"
        assert tool.annotations.read_only and not tool.annotations.destructive
        schema = probatio.to_json_schema(tool.parameters)
        assert schema["type"] == "object"
        assert "api_key" not in schema.get("properties", {})


async def test_search_tool_returns_action_response_and_context(hass, entry, monkeypatch):
    instance = await setup_provider(hass, entry, monkeypatch)
    expected = {"count": 1, "places": [{"place_name": "서울역", "latitude": 37.55, "longitude": 126.97}]}
    entry.runtime_data.async_search = AsyncMock(return_value=expected)
    call = hass.services.async_call
    spy = AsyncMock(wraps=call)
    monkeypatch.setattr(type(hass.services), "async_call", spy)
    result = await instance.async_call_tool(llm.ToolInput(
        tool_name="kakaomap__search_places", tool_args={"name": "서울역"}
    ))
    assert isinstance(result, llm.ToolResult) and result.data == expected
    assert not result.error
    assert spy.call_args.kwargs["context"] is instance.llm_context.context
    entry.runtime_data.async_search.assert_awaited_once_with(name="서울역", address="", limit=5)


@pytest.mark.parametrize("mode", [None, "walk", "bicycle"])
async def test_route_tool_defaults_to_transit(hass, entry, monkeypatch, mode):
    instance = await setup_provider(hass, entry, monkeypatch)
    expected = {"count": 0, "routes": []}
    entry.runtime_data.async_get_route = AsyncMock(return_value=expected)
    inputs = {"start_latitude": 37.5, "start_longitude": 127.0,
              "end_latitude": 37.6, "end_longitude": 127.1}
    if mode:
        inputs["mode"] = mode
    result = await instance.async_call_tool(llm.ToolInput(
        tool_name="kakaomap__get_route", tool_args=inputs
    ))
    assert result.data == expected
    assert entry.runtime_data.async_get_route.call_args.kwargs["mode"] == (mode or "public_transport")


async def test_home_tool_and_fresh_location(hass, entry, monkeypatch):
    instance = await setup_provider(hass, entry, monkeypatch)
    hass.config.latitude, hass.config.longitude = 37.5, 127.0
    result = await instance.async_call_tool(llm.ToolInput(
        tool_name="kakaomap__get_home_location", tool_args={}
    ))
    assert result.data == {"name": "집", "latitude": 37.5, "longitude": 127.0}
    hass.config.latitude = 37.6
    updated = await instance.async_call_tool(llm.ToolInput(
        tool_name="kakaomap__get_home_location", tool_args={}
    ))
    assert updated.data["latitude"] == 37.6
    assert "127.0" not in instance.api_prompt


@pytest.mark.parametrize("name,args", [
    ("kakaomap__get_route", {}),
    ("kakaomap__get_route", {"start_latitude": 37.5, "start_longitude": 127.0,
                            "end_latitude": 37.6, "end_longitude": 127.1, "mode": "car"}),
    ("kakaomap__search_places", {"name": "서울역", "api_key": "untrusted-extra-field"}),
    ("kakaomap__get_home_location", {"extra": True}),
])
async def test_invalid_args_fail_before_service_call(hass, entry, monkeypatch, name, args):
    instance = await setup_provider(hass, entry, monkeypatch)
    spy = AsyncMock()
    monkeypatch.setattr(type(hass.services), "async_call", spy)
    with pytest.raises(ServiceValidationError):
        await instance.async_call_tool(llm.ToolInput(tool_name=name, tool_args=args))
    spy.assert_not_awaited()


async def test_action_error_is_preserved(hass, entry, monkeypatch):
    instance = await setup_provider(hass, entry, monkeypatch)
    entry.runtime_data.async_search = AsyncMock(side_effect=integration.KakaoMapConnectionError)
    with pytest.raises(HomeAssistantError, match="연결"):
        await instance.async_call_tool(llm.ToolInput(
            tool_name="kakaomap__search_places", tool_args={"name": "서울역"}
        ))


async def test_unregister_reload_and_opt_in(hass, entry, monkeypatch):
    instance = await setup_provider(hass, entry, monkeypatch)
    assert async_get_tools(hass, instance.llm_context, "assist") is None
    await integration.async_unload_entry(hass, entry)
    # The config entry manager runs these callbacks after integration unload.
    await entry._async_process_on_unload(hass)
    assert llm.async_get_apis(hass) == []
    await integration.async_setup_entry(hass, entry)
    assert len(llm.async_get_apis(hass)) == 1


async def test_conversation_policy(hass, entry, monkeypatch):
    instance = await setup_provider(hass, entry, monkeypatch)
    assert "Default to public_transport" in instance.api_prompt
    assert "only when the user explicitly requests" in instance.api_prompt
    assert "Do not automatically switch" in instance.api_prompt
    assert "never invent coordinates" in instance.api_prompt
