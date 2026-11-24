"""Premier Inn calendar platform."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import hashlib
import json
import logging
import uuid

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BOOKING_CONFIRMATION,
    CONF_CALENDARS,
    CONF_HOTEL_INFORMATION,
    CONF_RES_NO,
    DOMAIN,
)
from .coordinator import PremierInnCoordinator

_LOGGER = logging.getLogger(__name__)
_CALENDAR_EXPORT_LOCK = f"{DOMAIN}_calendar_export_lock"

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
    """Set up the booking calendar and export events to selected calendars."""
    config = hass.data[DOMAIN][entry.entry_id]
    # Update our config to include new repos and remove those that have been removed.
    if entry.options:
        config.update(entry.options)

    session = async_get_clientsession(hass)
    coordinator = PremierInnCoordinator(hass, session, entry.data)

    await coordinator.async_refresh()

    name = entry.data[CONF_RES_NO]

    calendars = entry.data[CONF_CALENDARS]

    booking_calendar = PremierInnCalendarSensor(coordinator, name)

    if "None" in calendars:
        async_add_entities([booking_calendar], update_before_add=True)

    external_calendars = [calendar for calendar in calendars if calendar != "None"]
    if not external_calendars:
        return

    @callback
    def async_start_calendar_export(hass: HomeAssistant) -> None:
        entry.async_create_background_task(
            hass,
            async_export_events(hass, external_calendars, booking_calendar, entry),
            f"{DOMAIN} calendar export",
        )

    entry.async_on_unload(async_at_started(hass, async_start_calendar_export))


async def async_export_events(
    hass: HomeAssistant,
    calendars: list[str],
    booking_calendar: PremierInnCalendarSensor,
    entry: ConfigEntry,
) -> None:
    """Export upcoming booking events to each configured calendar."""
    events = booking_calendar.get_events(dt_util.now(), hass)
    # Older config flows could create multiple entries for the same booking.
    lock = hass.data.setdefault(_CALENDAR_EXPORT_LOCK, asyncio.Lock())
    for calendar in calendars:
        for event in events:
            async with lock:
                await add_to_calendar(hass, calendar, event, entry)


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


def calendar_event_matches(
    event_data: dict[str, str], description: str, start: datetime, end: datetime
) -> bool:
    """Compare the booking marker and event times from a calendar response."""
    if str(event_data.get("description", "")).strip().casefold() != description:
        return False

    return (
        datetime.fromisoformat(event_data["start"]) == start
        and datetime.fromisoformat(event_data["end"]) == end
    )


async def add_to_calendar(
    hass: HomeAssistant, calendar: str, event: CalendarEvent, entry: ConfigEntry
) -> None:
    """Add a booking event only when it is absent from the calendar."""
    if not isinstance(event.start, datetime) or not isinstance(event.end, datetime):
        return

    search_data = {
        "entity_id": calendar,
        "start_date_time": event.start,
        "end_date_time": event.end,
    }
    service_data = {
        **search_data,
        "summary": event.summary,
        "description": f"{event.description}",
        "location": f"{event.location}",
    }
    description = service_data["description"].strip().casefold()
    start = event.start.astimezone(UTC)
    end = event.end.astimezone(UTC)
    uid = generate_uuid_from_json(
        {"calendar": calendar, "description": description, "start": start, "end": end}
    )
    # Earlier versions hashed the full create_event payload.
    legacy_uid = generate_uuid_from_json(service_data)
    for booking in hass.config_entries.async_entries(DOMAIN):
        uids = booking.data.get("uids", [])
        if uid in uids or legacy_uid in uids:
            return

    try:
        response = await hass.services.async_call(
            "calendar", "get_events", search_data, blocking=True, return_response=True
        )
        calendar_data = response.get(calendar) if response is not None else None
        events = calendar_data.get("events") if isinstance(calendar_data, dict) else None
        if not isinstance(events, list):
            _LOGGER.warning("Could not read events from %s", calendar)
            return

        if not any(
            calendar_event_matches(event_data, description, start, end)
            for event_data in events
        ):
            await hass.services.async_call(
                "calendar", "create_event", service_data, blocking=True
            )
    except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
        _LOGGER.warning(
            "Could not export the Premier Inn booking to %s (%s)", calendar, err
        )
        return

    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "uids": [*entry.data.get("uids", []), uid]}
    )


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
