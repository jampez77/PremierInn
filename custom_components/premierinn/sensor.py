"""Premier Inn sensor platform."""

from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BOOKING_CONFIRMATION,
    CONF_HOTEL_INFORMATION,
    CONF_RES_NO,
    DOMAIN,
)
from .coordinator import PremierInnCoordinator

SENSOR_TYPES = [
    SensorEntityDescription(
        key="roomStay", name="Booking", icon="mdi:clipboard-outline"
    ),
    SensorEntityDescription(
        key="hotelInformation", name="Hotel Information", icon="mdi:bed"
    ),
    SensorEntityDescription(
        key="checkInTime",
        name="Check in Time",
        icon="mdi:clock-in",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="checkOutTime",
        name="Check out Time",
        icon="mdi:clock-out",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]


def hasBookingExpired(hass: HomeAssistant, expiry_date_raw: str) -> bool:
    """Check if booking has expired."""
    user_timezone = dt_util.get_time_zone(hass.config.time_zone)

    dt_utc = datetime.strptime(expiry_date_raw, "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=user_timezone
    )
    # Convert the datetime to the default timezone
    expiry_date = dt_utc.astimezone(user_timezone)

    return (expiry_date.timestamp() - datetime.today().timestamp()) <= 0


async def removeBooking(hass: HomeAssistant, booking_reference: str):
    """Remove expired booking."""
    entry = next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_RES_NO) == booking_reference
        ),
        None,
    )

    # Remove the config entry
    await hass.config_entries.async_remove(entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][entry.entry_id]

    if entry.options:
        config.update(entry.options)

    if entry.data:
        session = async_get_clientsession(hass)

        coordinator = PremierInnCoordinator(hass, session, entry.data)

        await coordinator.async_refresh()

        name = entry.data[CONF_RES_NO]

        room_stay = coordinator.data.get(CONF_BOOKING_CONFIRMATION)[
            "reservationByIdList"
        ][0]["roomStay"]

        check_out_time = f"{room_stay['departureDate']}T{room_stay['checkOutTime']}:00"

        if hasBookingExpired(hass, check_out_time):
            await removeBooking(hass, name)
        else:
            sensors = [
                PremierInnSensor(coordinator, name, description)
                for description in SENSOR_TYPES
            ]
            async_add_entities(sensors, update_before_add=True)


class PremierInnSensor(CoordinatorEntity[PremierInnCoordinator], SensorEntity):
    """Define an Premier Inn sensor."""

    def __init__(
        self,
        coordinator: PremierInnCoordinator,
        name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{name}")},
            manufacturer="Premier Inn",
            model=self.data.get(CONF_HOTEL_INFORMATION)["name"],
            name=name.upper(),
            configuration_url="https://github.com/jampez77/PremierInn/",
        )
        self._attr_unique_id = f"{DOMAIN}-{name}-{description.key}".lower()
        self.entity_id = f"sensor.{DOMAIN}_{name}_{description.key}".lower()
        self.attrs: dict[str, Any] = {}
        self.entity_description = description
        self.name = name
        self._state = None

    def update_from_coordinator(self):
        """Update sensor state and attributes from coordinator data."""
        room_stay = self.data.get(CONF_BOOKING_CONFIRMATION)["reservationByIdList"][0][
            "roomStay"
        ]

        check_out_time = f"{room_stay['departureDate']}T{room_stay['checkOutTime']}:00"

        if hasBookingExpired(self.hass, check_out_time):
            self.hass.async_add_job(removeBooking(self.hass, self.name))
        else:
            value = self.data.get(self.entity_description.key)

            if self.entity_description.key == "roomStay":
                room_stay = self.data.get(CONF_BOOKING_CONFIRMATION)[
                    "reservationByIdList"
                ][0]["roomStay"]

                value = room_stay["roomExtraInfo"]["roomName"]

            if self.entity_description.key == "hotelInformation":
                value = self.data.get(CONF_HOTEL_INFORMATION)["name"]

            if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
                room_stay = self.data.get(CONF_BOOKING_CONFIRMATION)[
                    "reservationByIdList"
                ][0]["roomStay"]

                if self.entity_description.key == "checkInTime":
                    value = f"{room_stay['arrivalDate']}T{room_stay['checkInTime']}:00"
                elif self.entity_description.key == "checkOutTime":
                    value = (
                        f"{room_stay['departureDate']}T{room_stay['checkOutTime']}:00"
                    )

                user_timezone = dt_util.get_time_zone(self.hass.config.time_zone)

                dt_utc = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S").replace(
                    tzinfo=user_timezone
                )
                # Convert the datetime to the default timezone
                value = dt_utc.astimezone(user_timezone)

            self._state = value

            if self.entity_description.key == "roomStay":
                value = self.data.get(CONF_BOOKING_CONFIRMATION)
            else:
                value = self.data.get(self.entity_description.key)

            if isinstance(value, (dict, list)):
                for index, attribute in enumerate(value):
                    if isinstance(attribute, (dict, list)):
                        for attr in attribute:
                            self.attrs[str(attr) + str(index)] = attribute[attr]
                    else:
                        self.attrs[attribute] = value[attribute]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_from_coordinator()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle adding to Home Assistant."""
        await super().async_added_to_hass()
        await self.async_update()

    async def async_remove(self) -> None:
        """Handle the removal of the entity."""
        # If you have any specific cleanup logic, add it here
        if self.hass is not None:
            await super().async_remove()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.data)

    @property
    def native_value(self) -> str | date | None:
        """Native value."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Define entity attributes."""
        return self.attrs
