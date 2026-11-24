"""The Premier Inn integration."""

from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .services import async_cleanup_services, async_setup_services

PLATFORMS = [Platform.CALENDAR, Platform.GEO_LOCATION, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    # Register services when the first config entry is added
    if not hass.data[DOMAIN]:
        async_setup_services(hass)

    options = entry.options

    async def reload_on_options_change(
        hass: HomeAssistant, updated_entry: ConfigEntry
    ) -> None:
        if (
            updated_entry.options != options
            and updated_entry.state
            not in (ConfigEntryState.SETUP_IN_PROGRESS, ConfigEntryState.SETUP_RETRY)
        ):
            await hass.config_entries.async_reload(updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(reload_on_options_change))

    hass.data[DOMAIN][entry.entry_id] = hass_data
    # Forward the setup to each platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    # Remove config entry from domain.
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    # If this was the last config entry, unregister the services
    if not hass.data[DOMAIN]:
        async_cleanup_services(hass)

    return unload_ok
