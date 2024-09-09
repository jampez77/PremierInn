from homeassistant.core import HomeAssistant, ServiceCall
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from .const import (
    DOMAIN,
    CONF_RES_NO,
    CONF_ARRIVAL_DATE,
    CONF_CALENDARS,
    CONF_ADD_BOOKING,
    CONF_REMOVE_BOOKING,
    CONF_LAST_NAME,
    CONF_GREAT_BRITAIN,
    CONF_GERMANY,
    CONF_COUNTRY,
    CONF_DE,
    CONF_GB,
    CONF_CREATE_CALENDAR
)
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from .coordinator import PremierInnCoordinator
import functools


# Define the schema for your service
SERVICE_ADD_BOOKING_SCHEMA = vol.Schema(
    {
        **cv.ENTITY_SERVICE_FIELDS,
        vol.Required(CONF_CREATE_CALENDAR): cv.boolean,
        vol.Required(CONF_ARRIVAL_DATE): cv.string,
        vol.Required(CONF_LAST_NAME): cv.string,
        vol.Required(CONF_RES_NO): cv.string,
        vol.Required(CONF_COUNTRY, default=CONF_GREAT_BRITAIN): vol.In([CONF_GREAT_BRITAIN, CONF_GERMANY]),

    }
)

SERVICE_REMOVE_BOOKING_SCHEMA = vol.Schema({
    vol.Required(CONF_RES_NO): cv.string,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Premier Inn from a config entry."""

    # Create a coordinator or other necessary components
    session = async_get_clientsession(hass)
    coordinator = PremierInnCoordinator(hass, session, entry.data)

    # Store the coordinator so it can be accessed by other parts of the integration
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Setup the service (if it hasn't already been set up globally)
    async_setup_services(hass)

    # You may also register entities, update the coordinator, etc.
    await coordinator.async_refresh()

    if coordinator.last_exception is not None:
        return False

    return True


def async_cleanup_services(hass: HomeAssistant) -> None:
    """Cleanup Premier Inn services."""
    hass.services.async_remove(DOMAIN, CONF_ADD_BOOKING)
    hass.services.async_remove(DOMAIN, CONF_REMOVE_BOOKING)


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Premier Inn services."""
    services = [
        (
            CONF_ADD_BOOKING,
            functools.partial(add_booking, hass),
            SERVICE_ADD_BOOKING_SCHEMA,
        ),
        (
            CONF_REMOVE_BOOKING,
            functools.partial(remove_booking, hass),
            SERVICE_REMOVE_BOOKING_SCHEMA,
        )
    ]
    for name, method, schema in services:
        if hass.services.has_service(DOMAIN, name):
            continue
        hass.services.async_register(DOMAIN, name, method, schema=schema)


def get_country(data: dict) -> str:
    if CONF_COUNTRY in data and data[CONF_COUNTRY] == CONF_GERMANY:
        return CONF_DE
    return CONF_GB


async def add_booking(hass: HomeAssistant, call: ServiceCall) -> None:
    """ Add a Premier Inn booking"""
    booking_reference = call.data.get(CONF_RES_NO)
    arrival_date = call.data.get(CONF_ARRIVAL_DATE)
    surname = call.data.get(CONF_LAST_NAME)
    country = get_country(call.data)
    create_calendar = call.data.get(CONF_CREATE_CALENDAR)
    calendars = call.data.get(CONF_ENTITY_ID)

    calendar_entities = {}

    if create_calendar:
        calendar_entities["None"] = "Create a new calendar"

    for calendar in calendars:
        calendar_entity = hass.states.get(calendar)
        if calendar_entity:
            calendar_entities[calendar] = calendar

    entries = hass.config_entries.async_entries(DOMAIN)

    if any(entry.data.get(CONF_RES_NO) == booking_reference for entry in entries):
        return

    # Initiate the config flow with the "import" step
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data={
            CONF_RES_NO: booking_reference,
            CONF_ARRIVAL_DATE: arrival_date,
            CONF_LAST_NAME: surname,
            CONF_COUNTRY: country,
            CONF_CALENDARS: calendar_entities
        }
    )

    # Notify user
    hass.components.persistent_notification.create(
        f"Added Premier Inn booking {booking_reference}",
        title="Premier Inn Booking Added"
    )


async def remove_booking(hass: HomeAssistant, call: ServiceCall) -> None:
    """Remove a booking, its device, and all related entities."""
    booking_reference = call.data.get(CONF_RES_NO)

    # Find the config entry corresponding to the booking reference
    entry = next(
        (entry for entry in hass.config_entries.async_entries(DOMAIN)
         if entry.data.get(CONF_RES_NO) == booking_reference),
        None
    )

    # Remove the config entry
    await hass.config_entries.async_remove(entry.entry_id)
