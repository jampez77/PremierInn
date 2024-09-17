"""Premier Inn Geo location platform."""

import logging
from typing import Any

from bs4 import BeautifulSoup

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import (
    CONF_BOOKING_CONFIRMATION,
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

    sensors = [PremierInnGeolocationEvent(coordinator, name)]
    async_add_entities(sensors, update_before_add=True)


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
        self._attr_unique_id = f"{DOMAIN}-{self.hotel_name}".lower()
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
