"""Test actual HA response action calls; related files: __init__.py, services.yaml."""

from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

import custom_components.kakaomap as integration
from custom_components.kakaomap.api import KakaoMapAuthError


async def test_service_response_and_unload(hass, entry, monkeypatch):
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: Mock())
    await integration.async_setup_entry(hass, entry)
    expected = {"places": [], "count": 0}
    entry.runtime_data.async_search = AsyncMock(return_value=expected)
    assert hass.services.supports_response("kakaomap", "search_places") == SupportsResponse.ONLY
    result = await hass.services.async_call(
        "kakaomap", "search_places", {"name": "서울역"}, blocking=True, return_response=True
    )
    assert result == expected
    entry.runtime_data.async_search.assert_awaited_once_with(name="서울역", address="", limit=5)
    await integration.async_unload_entry(hass, entry)
    assert not hass.services.has_service("kakaomap", "search_places")


async def test_empty_query_raises_validation_error(hass, entry, monkeypatch):
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: Mock())
    await integration.async_setup_entry(hass, entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("kakaomap", "search_places", {}, blocking=True, return_response=True)


async def test_auth_failure_starts_reauth(hass, entry, monkeypatch):
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: Mock())
    await integration.async_setup_entry(hass, entry)
    entry.runtime_data.async_search = AsyncMock(side_effect=KakaoMapAuthError)
    start_reauth = Mock()
    monkeypatch.setattr(type(entry), "async_start_reauth", start_reauth)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("kakaomap", "search_places", {"name": "서울역"},
                                      blocking=True, return_response=True)
    start_reauth.assert_called_once_with(hass)
