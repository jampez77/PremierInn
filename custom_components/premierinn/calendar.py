"""Premier Inn sensor platform."""

from datetime import datetime
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.exceptions import ServiceValidationError, HomeAssistantError
from .const import (
    DOMAIN,
    CONF_RES_NO,
    CONF_CALENDARS,
    CONF_HOTEL_INFORMATION,
    CONF_BOOKING_CONFIRMATION,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
import uuid
import hashlib
import json
from .coordinator import PremierInnCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)

DATE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="holiday",
        name="Holiday",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][entry.entry_id]
    # Update our config to include new repos and remove those that have been removed.
    if entry.options:
        config.update(entry.options)

    session = async_get_clientsession(hass)
    coordinator = PremierInnCoordinator(hass, session, entry.data)

    await coordinator.async_refresh()

    name = entry.data[CONF_RES_NO]

    calendars = entry.data[CONF_CALENDARS]

    sensors = [PremierInnCalendarSensor(coordinator, name)]

    for calendar in calendars:
        if calendar != "None":
            for sensor in sensors:
                events = sensor.get_events(datetime.today(), hass)
                for event in events:
                    await add_to_calendar(hass, calendar, event, entry)

    if "None" in calendars:
        async_add_entities(sensors, update_before_add=True)


async def create_event(hass: HomeAssistant, service_data):
    """Create calendar event."""
    try:
        await hass.services.async_call(
            "calendar",
            "create_event",
            service_data,
            blocking=True,
            return_response=True,
        )
    except (ServiceValidationError, HomeAssistantError):
        await hass.services.async_call(
            "calendar",
            "create_event",
            service_data,
            blocking=True,
        )


class DateTimeEncoder(json.JSONEncoder):
    """Encode date time object."""

    def default(self, o):
        """Encode date time object."""
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def generate_uuid_from_json(json_obj):
    """Generate a UUID from a JSON object."""

    json_string = json.dumps(json_obj, cls=DateTimeEncoder, sort_keys=True)

    sha1_hash = hashlib.sha1(json_string.encode("utf-8")).digest()

    return str(uuid.UUID(bytes=sha1_hash[:16]))


async def get_event_uid(hass: HomeAssistant, service_data) -> str | None:
    """Fetch the created event by matching with details in service_data."""
    entity_id = service_data.get("entity_id")
    start_time = service_data.get("start_date_time")
    end_time = service_data.get("end_date_time")

    try:
        events = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": entity_id,
                "start_date_time": start_time,
                "end_date_time": end_time,
            },
            return_response=True,
            blocking=True,
        )
    except (ServiceValidationError, HomeAssistantError):
        events = None

    if events is not None and entity_id in events:
        for event in events[entity_id].get("events"):
            if (
                event["summary"] == service_data["summary"]
                and f"{event["description"]}" == f"{service_data["description"]}"
                and f"{event["location"]}" == f"{service_data["location"]}"
            ):
                return generate_uuid_from_json(service_data)

    return None


async def add_to_calendar(
    hass: HomeAssistant, calendar: str, event: CalendarEvent, entry: ConfigEntry
):
    """Add an event to the calendar."""

    service_data = {
        "entity_id": calendar,
        "start_date_time": event.start,
        "end_date_time": event.end,
        "summary": event.summary,
        "description": f"{event.description}",
        "location": f"{event.location}",
    }

    uid = await get_event_uid(hass, service_data)

    uids = entry.data.get("uids", [])

    if uid not in uids:
        await create_event(hass, service_data)

        created_event_uid = await get_event_uid(hass, service_data)

        if created_event_uid is not None and created_event_uid not in uids:
            uids.append(created_event_uid)

    if uids != entry.data.get("uids", []):
        updated_data = entry.data.copy()
        updated_data["uids"] = uids
        hass.config_entries.async_update_entry(entry, data=updated_data)


class PremierInnCalendarSensor(
    CoordinatorEntity[PremierInnCoordinator], CalendarEntity
):
    """Define an Premier Inn sensor."""

    def __init__(self, coordinator: PremierInnCoordinator, name: str) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.data = coordinator.data
        self.booking_confirmation = self.data.get(CONF_BOOKING_CONFIRMATION)
        self.room_stay = self.booking_confirmation["reservationByIdList"][0]["roomStay"]
        self.hotel_info = self.data.get(CONF_HOTEL_INFORMATION)
        self.event_name = "Premier Inn"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{name}")},
            manufacturer=self.event_name,
            model=self.hotel_info["name"],
            name=f'{self.event_name}: {self.room_stay["roomExtraInfo"]["roomName"]}',
            configuration_url="https://github.com/jampez77/PremierInn/",
        )
        self._attr_unique_id = f"{DOMAIN}-{name}-calendar".lower()
        self._attr_name = f"{DOMAIN.title()} - {name.upper()}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.data)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        events = self.get_events(datetime.today(), self.hass)
        return sorted(events, key=lambda c: c.start)[0]

    def get_events(
        self, start_date: datetime, hass: HomeAssistant
    ) -> list[CalendarEvent]:
        """Return calendar events."""
        events = []

        for date_sensor_type in DATE_SENSOR_TYPES:
            event_end_raw = None
            event_description = (
                f"PremierInn|{self.booking_confirmation["bookingReference"]}"
            )
            formatted_address = [
                value
                for key, value in self.hotel_info["address"].items()
                if value and value not in {"None", ""} and key != "country"
            ]

            event_location = ", ".join(formatted_address)
            event_name = date_sensor_type.name

            event_start_raw = (
                f"{self.room_stay['arrivalDate']}T{self.room_stay['checkInTime']}:00"
            )
            event_end_raw = (
                f"{self.room_stay['departureDate']}T{self.room_stay['checkOutTime']}:00"
            )

            event_name = (
                f'{self.event_name}: {self.room_stay["roomExtraInfo"]["roomName"]}'
            )

            if not event_start_raw:
                continue

            user_timezone = dt_util.get_time_zone(hass.config.time_zone)

            start_dt_utc = datetime.strptime(
                event_start_raw, "%Y-%m-%dT%H:%M:%S"
            ).replace(tzinfo=user_timezone)
            # Convert the datetime to the default timezone
            event_start = start_dt_utc.astimezone(user_timezone)

            if event_end_raw is None:
                event_end_raw = event_start_raw

            end_dt_utc = datetime.strptime(event_end_raw, "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=user_timezone
            )
            # Convert the datetime to the default timezone
            event_end = end_dt_utc.astimezone(user_timezone)

            if event_start.date() >= start_date.date():
                events.append(
                    CalendarEvent(
                        start=event_start,
                        end=event_end,
                        summary=event_name,
                        location=event_location,
                        description=event_description,
                    )
                )
        return events

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            event
            for event in self.get_events(start_date, hass)
            if event.start.date() <= end_date.date()
        ]
