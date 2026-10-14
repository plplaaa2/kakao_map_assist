"""Register response actions; related files: api.py, routes.py, config_flow.py, services.yaml."""

from __future__ import annotations

import logging

import probatio as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm as ha_llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    KakaoMapAuthError, KakaoMapClient, KakaoMapConnectionError,
    KakaoMapPermissionError, KakaoMapRateLimitError, KakaoMapResponseError, KakaoMapRouteError,
)
from .const import DEFAULT_LIMIT, DOMAIN, ROUTE_URLS, SERVICE_GET_ROUTE, SERVICE_SEARCH_PLACES

_LOGGER = logging.getLogger(__name__)
type KakaoMapConfigEntry = ConfigEntry[KakaoMapClient]

SEARCH_SCHEMA = vol.Schema({
    vol.Optional("name", default=""): cv.string,
    vol.Optional("address", default=""): cv.string,
    vol.Optional("limit", default=DEFAULT_LIMIT): vol.All(cv.positive_int, vol.Range(min=1, max=15)),
})

# Route action schema; related files: api.py, routes.py, services.yaml.
ROUTE_SCHEMA = vol.Schema({
    vol.Required("start_latitude"): cv.latitude,
    vol.Required("start_longitude"): cv.longitude,
    vol.Required("end_latitude"): cv.latitude,
    vol.Required("end_longitude"): cv.longitude,
    vol.Optional("mode", default="public_transport"): vol.In(ROUTE_URLS),
    vol.Optional("start_name", default="출발"): cv.string,
    vol.Optional("end_name", default="도착"): cv.string,
})


async def async_setup_entry(hass: HomeAssistant, entry: KakaoMapConfigEntry) -> bool:
    """Create a client and expose on-demand place and route response actions."""
    # Register the Assist provider with entry-scoped cleanup; related file: llm.py.
    from .llm import KakaoMapAPI

    entry.async_on_unload(ha_llm.async_register_api(hass, KakaoMapAPI(
        hass=hass, id=f"{DOMAIN}-{entry.entry_id}", name="KakaoMap",
    )))
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

    async def async_get_route(call: ServiceCall) -> ServiceResponse:
        """Return route summaries; related files: api.py, routes.py, services.yaml."""
        try:
            return await entry.runtime_data.async_get_route(**call.data)
        except ValueError:
            raise ServiceValidationError("출발·도착 위도와 경도 및 이동 수단을 확인하세요. 출발·도착지는 서로 달라야 합니다.") from None
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
            raise HomeAssistantError("카카오 API가 요청을 거부했거나 올바르지 않은 경로를 반환했습니다.") from None
        except KakaoMapRouteError as error:
            raise HomeAssistantError(str(error)) from None

    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH_PLACES, async_search_places,
        schema=SEARCH_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_ROUTE, async_get_route,
        schema=ROUTE_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
    _LOGGER.info("KakaoMap search and route actions are ready")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KakaoMapConfigEntry) -> bool:
    """Remove both actions when their connection is unloaded."""
    hass.services.async_remove(DOMAIN, SERVICE_SEARCH_PLACES)
    hass.services.async_remove(DOMAIN, SERVICE_GET_ROUTE)
    _LOGGER.info("KakaoMap search and route actions were unloaded")
    return True
