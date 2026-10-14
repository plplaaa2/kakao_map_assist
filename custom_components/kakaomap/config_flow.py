"""API-key setup and replacement; related files: api.py, strings.json, manifest.json."""

from __future__ import annotations

from typing import Any

import probatio as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import (
    KakaoMapAuthError, KakaoMapClient, KakaoMapConnectionError,
    KakaoMapPermissionError, KakaoMapRateLimitError, KakaoMapResponseError,
)
from .const import DOMAIN
from .notifications import async_dismiss_auth_notification

KEY_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD)
)})


class KakaoMapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one KakaoMap connection without exposing credentials."""

    VERSION = 1

    async def _async_key_form(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if not api_key or any(char.isspace() for char in api_key):
                errors["base"] = "invalid_auth"
            else:
                client = KakaoMapClient(async_get_clientsession(self.hass), api_key)
                try:
                    await client.async_validate()
                except KakaoMapAuthError:
                    errors["base"] = "invalid_auth"
                except KakaoMapPermissionError:
                    errors["base"] = "permission_denied"
                except KakaoMapRateLimitError:
                    errors["base"] = "rate_limited"
                except KakaoMapConnectionError:
                    errors["base"] = "cannot_connect"
                except KakaoMapResponseError:
                    errors["base"] = "invalid_response"
                else:
                    data = {CONF_API_KEY: api_key}
                    if step_id == "user":
                        self._async_abort_entries_match()
                        return self.async_create_entry(title="KakaoMap", data=data)
                    entry = (self._get_reauth_entry() if step_id == "reauth_confirm"
                             else self._get_reconfigure_entry())
                    result = self.async_update_reload_and_abort(
                        entry, data_updates=data,
                        reason="reauth_successful" if step_id == "reauth_confirm"
                        else "reconfigure_successful",
                    )
                    # Clear the alert only after validation and saving; see notifications.py.
                    async_dismiss_auth_notification(self.hass, entry.entry_id)
                    return result
        return self.async_show_form(step_id=step_id, data_schema=KEY_SCHEMA, errors=errors)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Add the single connection."""
        self._async_abort_entries_match()
        return await self._async_key_form("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Replace the key without creating another entry."""
        return await self._async_key_form("reconfigure", user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Ask for replacement credentials after authentication failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Validate and save replacement credentials."""
        return await self._async_key_form("reauth_confirm", user_input)
