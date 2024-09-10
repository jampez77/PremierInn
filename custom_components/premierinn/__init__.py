"""The Premier Inn integration."""
from __future__ import annotations
import asyncio
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from .const import DOMAIN
from .services import async_setup_services, async_cleanup_services
import homeassistant.helpers.config_validation as cv

PLATFORMS = [
    Platform.SENSOR,
    Platform.CALENDAR,
    Platform.GEO_LOCATION
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    # Register services when the first config entry is added
    if not hass.data[DOMAIN]:
        async_setup_services(hass)

    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(
        options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data
    # Forward the setup to each platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    entry_state = hass.config_entries.async_get_entry(
        config_entry.entry_id).state

    # Proceed only if the entry is in a valid state (loaded, etc.)
    if entry_state not in (ConfigEntryState.SETUP_IN_PROGRESS, ConfigEntryState.SETUP_RETRY):
        await hass.config_entries.async_reload(config_entry.entry_id)
    else:
        print(
            f"Cannot reload entry {config_entry.entry_id}, still in setup progress.")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(entry, platform) for platform in PLATFORMS]
        )
    )
    # Remove options_update_listener.
    hass.data[DOMAIN][entry.entry_id]["unsub_options_update_listener"]()
    # Remove config entry from domain.
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    # If this was the last config entry, unregister the services
    if not hass.data[DOMAIN]:
        async_cleanup_services(hass)

    return unload_ok


async def handle_get_events(call: ServiceCall) -> None:
    # Your logic to handle the service call
    pass


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Premier Inn component from yaml configuration."""

    hass.services.async_register("calendar", "list_events", handle_get_events)
    hass.data.setdefault(DOMAIN, {})
    return True
