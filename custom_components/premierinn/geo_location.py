"""Premier Inn Geo location platform."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import (
    CONF_BOOKING_CONFIRMATION,
    CONF_HOTEL_ID,
    CONF_HOTEL_INFORMATION,
    CONF_RES_NO,
    DOMAIN,
)
from .coordinator import PremierInnCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the geolocation platform."""

    config = hass.data[DOMAIN][entry.entry_id]
    # Update our config to include new repos and remove those that have been removed.
    if entry.options:
        config.update(entry.options)

    session = async_get_clientsession(hass)
    coordinator = PremierInnCoordinator(hass, session, entry.data)

    await coordinator.async_refresh()

    name = entry.data[CONF_RES_NO]

    location = PremierInnGeolocationEvent(coordinator, name)
    _migrate_location_unique_id(hass, entry, location)
    async_add_entities([location], update_before_add=True)


def _migrate_location_unique_id(
    hass: HomeAssistant, entry: ConfigEntry, location: PremierInnGeolocationEvent
) -> None:
    """Reuse the existing registry entry when its hotel can be identified."""
    registry = er.async_get(hass)
    if registry.async_get_entity_id(Platform.GEO_LOCATION, DOMAIN, location.unique_id):
        return

    legacy_entries = {
        entity.unique_id: entity
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity.domain == Platform.GEO_LOCATION
        and entity.platform == DOMAIN
        and entity.unique_id.startswith(f"{DOMAIN}-")
    }
    legacy_entry = legacy_entries.get(f"{DOMAIN}-{location.hotel_name}".lower())
    # A renamed hotel can leave a single legacy row for this booking.
    if legacy_entry is None and len(legacy_entries) == 1:
        legacy_entry = next(iter(legacy_entries.values()))
    if legacy_entry is not None:
        registry.async_update_entity(
            legacy_entry.entity_id, new_unique_id=location.unique_id
        )


class PremierInnGeolocationEvent(
    CoordinatorEntity[PremierInnCoordinator], GeolocationEvent
):
    """Representation of a geolocation entity."""

    _attr_should_poll = False
    _attr_source = DOMAIN

    def __init__(
        self,
        coordinator: PremierInnCoordinator,
        name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.data = coordinator.data
        self.booking_confirmation = self.data.get(CONF_BOOKING_CONFIRMATION)
        self.hotel_info = self.data.get(CONF_HOTEL_INFORMATION)
        self.hotel_name = self.hotel_info["name"]
        self.hotel_coordinates = self.hotel_info["coordinates"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{name}")},
            manufacturer="Premier Inn",
            model=self.hotel_name,
            name=name.upper(),
            configuration_url="https://github.com/jampez77/PremierInn/",
        )
        self._attr_unique_id = f"hotel:{self.booking_confirmation[CONF_HOTEL_ID]}"
        self.entity_id = f"geo_location.{DOMAIN}_{self.hotel_name}".lower()
        self.attrs: dict[str, Any] = {}
        self._attr_name = "Premier Inn - " + self.hotel_name
        self._attr_latitude = self.hotel_coordinates[ATTR_LATITUDE]
        self._attr_longitude = self.hotel_coordinates[ATTR_LONGITUDE]
        self._attr_accuracy = None
        self.formatted_address = [
            value
            for key, value in self.hotel_info["address"].items()
            if value and value not in {"None", ""} and key != "country"
        ]

    @property
    def state(self) -> str | None:
        """Return the state of the entity."""
        return ", ".join(self.formatted_address)

    @property
    def icon(self) -> str:
        """Return a representative icon of the hotel."""
        return "mdi:home-modern"

    async def async_update(self) -> None:
        """Fetch new state data for the entity."""
        try:
            self._attr_latitude = self.hotel_coordinates["latitude"]
            self._attr_longitude = self.hotel_coordinates["longitude"]
        except Exception as e:
            _LOGGER.error("Error updating geolocation: %s", e)
            raise UpdateFailed("Failed to update location data") from e

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""

        formatted_contact = [
            value
            for key, value in self.hotel_info["contactDetails"].items()
            if value and value not in {"None", ""}
        ]

        parkingSoup = BeautifulSoup(
            self.hotel_info.get("parkingDescription", "Not provided"), "html.parser"
        )
        parking = parkingSoup.get_text()

        directionsSoup = BeautifulSoup(
            self.hotel_info.get("directions", "Not provided"), "html.parser"
        )
        directions = directionsSoup.get_text()

        return {
            "Booking Reference": self.booking_confirmation["bookingReference"],
            "Parking": parking,
            "Directions": directions,
            "Address": ", ".join(self.formatted_address),
            "Contact": ", ".join(formatted_contact),
        }
