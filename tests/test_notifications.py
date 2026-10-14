"""Verify HA authentication alert lifecycle; related files: notifications.py, config_flow.py."""

from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.components import persistent_notification
from homeassistant.const import CONF_API_KEY
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.core import Context

import custom_components.kakaomap as integration
from custom_components.kakaomap import config_flow
from custom_components.kakaomap.api import (
    KakaoMapAuthError, KakaoMapConnectionError, KakaoMapPermissionError,
    KakaoMapRateLimitError, KakaoMapResponseError,
)
from custom_components.kakaomap.notifications import (
    async_notify_auth_failure, auth_notification_id,
)

ROUTE_DATA = {"start_latitude": 37.5, "start_longitude": 127.0,
              "end_latitude": 37.6, "end_longitude": 127.1}


@pytest.mark.parametrize("service,method,data", [
    ("search_places", "async_search", {"name": "서울역"}),
    ("get_route", "async_get_route", ROUTE_DATA),
])
async def test_auth_failure_creates_one_notification(hass, entry, monkeypatch, service, method, data):
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: Mock())
    reauth = Mock()
    monkeypatch.setattr(type(entry), "async_start_reauth", reauth)
    await integration.async_setup_entry(hass, entry)
    setattr(entry.runtime_data, method, AsyncMock(side_effect=KakaoMapAuthError))
    for _ in range(2):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call("kakaomap", service, data, blocking=True, return_response=True)
    notifications = hass.data[persistent_notification.DOMAIN]
    assert len(notifications) == 1
    notification = notifications[auth_notification_id(entry.entry_id)]
    assert notification["title"] == "KakaoMap API 키 확인 필요"
    assert "재인증" in notification["message"]
    assert entry.data[CONF_API_KEY] not in notification["message"]
    assert "만료되었습니다" not in notification["message"]
    assert reauth.call_count == 2


@pytest.mark.parametrize("error", [KakaoMapConnectionError, KakaoMapPermissionError,
                                   KakaoMapRateLimitError, KakaoMapResponseError])
async def test_other_errors_do_not_create_auth_alert(hass, entry, monkeypatch, error):
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: Mock())
    await integration.async_setup_entry(hass, entry)
    entry.runtime_data.async_search = AsyncMock(side_effect=error)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("kakaomap", "search_places", {"name": "서울역"},
                                      blocking=True, return_response=True)
    assert auth_notification_id(entry.entry_id) not in hass.data.get(persistent_notification.DOMAIN, {})


def make_replacement_flow(hass, entry, monkeypatch, source):
    hass.config_entries._entries[entry.entry_id] = entry
    flow = config_flow.KakaoMapConfigFlow()
    flow.hass = hass
    flow.context = {"source": source, "entry_id": entry.entry_id}
    flow.handler = "kakaomap"
    monkeypatch.setattr(config_flow, "async_get_clientsession", lambda hass: Mock())
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", Mock())
    return flow


@pytest.mark.parametrize("source,step", [("reauth", "async_step_reauth_confirm"),
                                       ("reconfigure", "async_step_reconfigure")])
async def test_successful_key_save_dismisses_only_own_alert(hass, entry, monkeypatch, source, step):
    async_notify_auth_failure(hass, entry.entry_id)
    persistent_notification.async_create(hass, "Other alert", notification_id="unrelated")
    flow = make_replacement_flow(hass, entry, monkeypatch, source)
    monkeypatch.setattr(config_flow.KakaoMapClient, "async_validate", AsyncMock())
    result = await getattr(flow, step)({CONF_API_KEY: "replacement-test-key"})
    assert result["type"] == "abort"
    assert entry.data[CONF_API_KEY] == "replacement-test-key"
    assert set(hass.data[persistent_notification.DOMAIN]) == {"unrelated"}


@pytest.mark.parametrize("source,step", [("reauth", "async_step_reauth_confirm"),
                                       ("reconfigure", "async_step_reconfigure")])
async def test_failed_key_validation_keeps_alert(hass, entry, monkeypatch, source, step):
    async_notify_auth_failure(hass, entry.entry_id)
    flow = make_replacement_flow(hass, entry, monkeypatch, source)
    monkeypatch.setattr(config_flow.KakaoMapClient, "async_validate", AsyncMock(side_effect=KakaoMapAuthError))
    result = await getattr(flow, step)({CONF_API_KEY: "invalid-test-key"})
    assert result["errors"] == {"base": "invalid_auth"}
    assert auth_notification_id(entry.entry_id) in hass.data[persistent_notification.DOMAIN]
    assert entry.data[CONF_API_KEY] == "not-a-real-key"


async def test_conversation_auth_error_also_notifies(hass, entry, monkeypatch):
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: Mock())
    monkeypatch.setattr(type(entry), "async_start_reauth", Mock())
    await integration.async_setup_entry(hass, entry)
    entry.runtime_data.async_search = AsyncMock(side_effect=KakaoMapAuthError)
    instance = await llm.async_get_api(hass, f"kakaomap-{entry.entry_id}", llm.LLMContext(
        platform="test_agent", context=Context(), language="ko", assistant="conversation", device_id=None
    ))
    with pytest.raises(HomeAssistantError):
        await instance.async_call_tool(llm.ToolInput(
            tool_name="kakaomap__search_places", tool_args={"name": "서울역"}
        ))
    assert auth_notification_id(entry.entry_id) in hass.data[persistent_notification.DOMAIN]
