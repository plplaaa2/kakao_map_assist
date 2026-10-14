"""Authentication alerts; related files: __init__.py, config_flow.py, manifest.json."""

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


def auth_notification_id(entry_id: str) -> str:
    """Use one stable ID per connection to avoid duplicate alerts."""
    return f"{DOMAIN}_auth_{entry_id}"


@callback
def async_notify_auth_failure(hass: HomeAssistant, entry_id: str) -> None:
    """Show a safe authentication notice without keys or upstream payloads."""
    persistent_notification.async_create(
        hass,
        "카카오맵 API 인증에 실패했습니다. API 키가 변경·폐기되었거나 유효하지 않을 수 있습니다. "
        "설정 → 기기 및 서비스 → KakaoMap에서 재인증 또는 재설정을 통해 "
        "사용 가능한 REST API 키를 등록하세요. 정상적으로 저장하면 이 알림은 자동으로 해제됩니다.",
        title="KakaoMap API 키 확인 필요",
        notification_id=auth_notification_id(entry_id),
    )


@callback
def async_dismiss_auth_notification(hass: HomeAssistant, entry_id: str) -> None:
    """Dismiss only this connection's alert after credentials are saved."""
    persistent_notification.async_dismiss(hass, auth_notification_id(entry_id))
