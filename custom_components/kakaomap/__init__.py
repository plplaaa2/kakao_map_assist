"""Register the response action; related files: api.py, config_flow.py, services.yaml."""

from __future__ import annotations

import logging

import probatio as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    KakaoMapAuthError, KakaoMapClient, KakaoMapConnectionError,
    KakaoMapPermissionError, KakaoMapRateLimitError, KakaoMapResponseError,
)
from .const import DEFAULT_LIMIT, DOMAIN, SERVICE_SEARCH_PLACES

_LOGGER = logging.getLogger(__name__)
type KakaoMapConfigEntry = ConfigEntry[KakaoMapClient]

SEARCH_SCHEMA = vol.Schema({
    vol.Optional("name", default=""): cv.string,
    vol.Optional("address", default=""): cv.string,
    vol.Optional("limit", default=DEFAULT_LIMIT): vol.All(cv.positive_int, vol.Range(min=1, max=15)),
})


async def async_setup_entry(hass: HomeAssistant, entry: KakaoMapConfigEntry) -> bool:
    """Create a client and expose one on-demand response action."""
    entry.runtime_data = KakaoMapClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])

    async def async_search_places(call: ServiceCall) -> ServiceResponse:
        """Search by name/address; never include keys in error messages."""
        try:
            return await entry.runtime_data.async_search(
                name=call.data["name"], address=call.data["address"], limit=call.data["limit"]
            )
        except ValueError:
            raise ServiceValidationError("장소명 또는 주소를 입력하고 결과 수를 1~15로 지정하세요.") from None
        except KakaoMapAuthError:
            entry.async_start_reauth(hass)
            raise HomeAssistantError("카카오 인증에 실패했습니다. 통합 설정에서 API 키를 다시 등록하세요.") from None
        except KakaoMapPermissionError:
            raise HomeAssistantError("카카오맵 API 활성화 및 REST API 키의 사용 권한을 확인하세요.") from None
        except KakaoMapRateLimitError:
            raise HomeAssistantError("카카오 API 호출 한도를 초과했습니다. 잠시 후 다시 시도하세요.") from None
        except KakaoMapConnectionError:
            raise HomeAssistantError("카카오 API에 연결할 수 없습니다. 잠시 후 다시 시도하세요.") from None
        except KakaoMapResponseError:
            raise HomeAssistantError("카카오 API가 요청을 거부했거나 올바르지 않은 결과를 반환했습니다.") from None

    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH_PLACES, async_search_places,
        schema=SEARCH_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
    _LOGGER.info("KakaoMap search action is ready")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KakaoMapConfigEntry) -> bool:
    """Remove the action when its connection is unloaded."""
    hass.services.async_remove(DOMAIN, SERVICE_SEARCH_PLACES)
    _LOGGER.info("KakaoMap search action was unloaded")
    return True
