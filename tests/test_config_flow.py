"""Validate setup/replacement flow outcomes; related files: config_flow.py, api.py."""

from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import AbortFlow

from custom_components.kakaomap import config_flow
from custom_components.kakaomap.api import (
    KakaoMapAuthError, KakaoMapConnectionError, KakaoMapPermissionError,
    KakaoMapRateLimitError, KakaoMapResponseError,
)


def make_flow(hass, monkeypatch, source="user"):
    flow = config_flow.KakaoMapConfigFlow()
    flow.hass = hass
    flow.context = {"source": source}
    flow.handler = "kakaomap"
    monkeypatch.setattr(config_flow, "async_get_clientsession", lambda hass: Mock())
    return flow


async def test_user_form_and_success(hass, monkeypatch):
    flow = make_flow(hass, monkeypatch)
    validate = AsyncMock()
    monkeypatch.setattr(config_flow.KakaoMapClient, "async_validate", validate)
    form = await flow.async_step_user()
    assert form["type"] == "form"
    result = await flow.async_step_user({CONF_API_KEY: " not-a-real-key "})
    assert result["type"] == "create_entry"
    assert result["data"][CONF_API_KEY] == "not-a-real-key"
    validate.assert_awaited_once()


@pytest.mark.parametrize("error,code", [
    (KakaoMapAuthError, "invalid_auth"), (KakaoMapPermissionError, "permission_denied"),
    (KakaoMapRateLimitError, "rate_limited"), (KakaoMapConnectionError, "cannot_connect"),
    (KakaoMapResponseError, "invalid_response"),
])
async def test_user_errors(hass, monkeypatch, error, code):
    flow = make_flow(hass, monkeypatch)
    monkeypatch.setattr(config_flow.KakaoMapClient, "async_validate", AsyncMock(side_effect=error))
    result = await flow.async_step_user({CONF_API_KEY: "not-a-real-key"})
    assert result["errors"] == {"base": code}


async def test_blank_key_does_not_call_api(hass, monkeypatch):
    flow = make_flow(hass, monkeypatch)
    validate = AsyncMock()
    monkeypatch.setattr(config_flow.KakaoMapClient, "async_validate", validate)
    result = await flow.async_step_user({CONF_API_KEY: " "})
    assert result["errors"] == {"base": "invalid_auth"}
    validate.assert_not_awaited()


async def test_duplicate_connection_aborts(hass, entry, monkeypatch):
    hass.config_entries._entries[entry.entry_id] = entry
    flow = make_flow(hass, monkeypatch)
    with pytest.raises(AbortFlow) as raised:
        await flow.async_step_user()
    assert raised.value.reason == "already_configured"


@pytest.mark.parametrize("source,step,reason", [
    ("reconfigure", "async_step_reconfigure", "reconfigure_successful"),
    ("reauth", "async_step_reauth_confirm", "reauth_successful"),
])
async def test_replacement_updates_existing_entry(hass, entry, monkeypatch, source, step, reason):
    hass.config_entries._entries[entry.entry_id] = entry
    flow = make_flow(hass, monkeypatch, source)
    flow.context["entry_id"] = entry.entry_id
    monkeypatch.setattr(config_flow.KakaoMapClient, "async_validate", AsyncMock())
    schedule = Mock()
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", schedule)
    result = await getattr(flow, step)({CONF_API_KEY: "replacement-test-key"})
    assert result["type"] == "abort"
    assert result["reason"] == reason
    assert entry.data[CONF_API_KEY] == "replacement-test-key"
    assert len(hass.config_entries.async_entries("kakaomap")) == 1
    schedule.assert_called_once_with(entry.entry_id)
