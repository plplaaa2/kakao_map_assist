"""Real HA runtime fixtures; related files: test_integration.py, test_config_flow.py."""

from types import MappingProxyType

import pytest
import pytest_asyncio

from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant


@pytest_asyncio.fixture
async def hass(tmp_path):
    """Create a real HA service registry without starting external integrations."""
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    yield instance
    await instance.async_block_till_done()
    await instance.async_stop()


@pytest.fixture
def entry():
    """Use an artificial credential only; no user secrets are needed."""
    return ConfigEntry(
        version=1, minor_version=1, domain="kakaomap", title="KakaoMap",
        data={CONF_API_KEY: "not-a-real-key"}, options={}, source="user",
        unique_id=None, discovery_keys=MappingProxyType({}), subentries_data=None,
    )
