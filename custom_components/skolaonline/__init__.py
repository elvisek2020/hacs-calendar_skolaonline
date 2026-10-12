"""Integrace Škola OnLine pro Home Assistant."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SkolaOnlineAuthError, SkolaOnlineClient, SkolaOnlineError
from .const import CONF_STUDENT_ID
from .coordinator import SkolaOnlineConfigEntry, SkolaOnlineCoordinator

PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: SkolaOnlineConfigEntry) -> bool:
    """Nastaví integraci z config entry."""
    client = SkolaOnlineClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    try:
        await client.async_login()
    except SkolaOnlineAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SkolaOnlineError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = SkolaOnlineCoordinator(
        hass, entry, client, entry.data[CONF_STUDENT_ID]
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SkolaOnlineConfigEntry
) -> bool:
    """Odstraní integraci."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
