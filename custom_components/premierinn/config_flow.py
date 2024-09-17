"""Config flow for Premier Inn integration."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.calendar import CalendarEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import EntityRegistry as er

from .const import (
    CONF_ARRIVAL_DATE,
    CONF_CALENDARS,
    CONF_COUNTRY,
    CONF_GERMANY,
    CONF_GREAT_BRITAIN,
    CONF_LAST_NAME,
    CONF_RES_NO,
    DOMAIN,
)
from .coordinator import PremierInnCoordinator

_LOGGER = logging.getLogger(__name__)


async def _get_calendar_entities(hass: HomeAssistant) -> list[str]:
    """Retrieve calendar entities."""
    entity_registry = er.async_get(hass)
    calendar_entities = {}
    for entity_id, entity in entity_registry.entities.items():
        if entity_id.startswith("calendar."):
            calendar_entity = hass.states.get(entity_id)
            if calendar_entity:
                supported_features = calendar_entity.attributes.get(
                    "supported_features", 0
                )

                supports_create_event = (
                    supported_features & CalendarEntityFeature.CREATE_EVENT
                )

                if supports_create_event:
                    calendar_name = entity.original_name or entity_id
                    calendar_entities[entity_id] = calendar_name

    calendar_entities["None"] = "Create a new calendar"
    return calendar_entities


def is_date_valid_format(value: str) -> bool:
    """Validate date input."""

    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    else:
        return True


@callback
def async_get_options_flow(config_entry):
    """PremierInn flow handler."""
    return PremierInnFlowHandler(config_entry)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    session = async_get_clientsession(hass)

    coordinator = PremierInnCoordinator(hass, session, data)

    await coordinator.async_refresh()

    if coordinator.last_exception is not None and data is not None:
        raise InvalidAuth

    return {"title": str(data[CONF_RES_NO]).upper()}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Premier Inn."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        calendar_entities = await _get_calendar_entities(self.hass)

        user_input = user_input or {}

        STEP_USER_DATA_SCHEMA = vol.Schema(
            {
                vol.Required(
                    CONF_ARRIVAL_DATE, default=user_input.get(CONF_ARRIVAL_DATE, "")
                ): cv.string,
                vol.Required(
                    CONF_LAST_NAME, default=user_input.get(CONF_LAST_NAME, "")
                ): cv.string,
                vol.Required(
                    CONF_RES_NO, default=user_input.get(CONF_RES_NO, "")
                ): cv.string,
                vol.Required(CONF_COUNTRY, default=CONF_GREAT_BRITAIN): vol.In(
                    [CONF_GREAT_BRITAIN, CONF_GERMANY]
                ),
                vol.Required(
                    CONF_CALENDARS, default=user_input.get(CONF_CALENDARS, [])
                ): cv.multi_select(calendar_entities),
            }
        )

        if user_input:
            entries = self.hass.config_entries.async_entries(DOMAIN)

            if any(
                entry.data.get(CONF_RES_NO) == user_input.get(CONF_RES_NO)
                for entry in entries
            ):
                errors["base"] = "booking_exists"

            if not user_input.get(CONF_CALENDARS):
                errors["base"] = "no_calendar_selected"

            if not user_input.get(CONF_COUNTRY):
                errors["base"] = "no_country_selected"

            if not is_date_valid_format(user_input.get(CONF_ARRIVAL_DATE)):
                errors["base"] = "invalid_date_format"

            if not errors:
                try:
                    info = await validate_input(self.hass, user_input)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data=None) -> FlowResult:
        """Handle the import step for the service call."""

        if import_data is not None:
            try:
                session = async_get_clientsession(self.hass)

                coordinator = PremierInnCoordinator(self.hass, session, import_data)

                await coordinator.async_refresh()

                if coordinator.data is not None:
                    await self.async_set_unique_id(import_data[CONF_RES_NO])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=import_data[CONF_RES_NO], data=import_data
                    )

                self.hass.components.persistent_notification.create(
                    f"Premier Inn booking {import_data[CONF_RES_NO].upper()} not found.",
                    title="Unable to add Premier Inn Booking",
                )
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.error("Failed to import booking: {e}")
                return self.async_abort(reason="import_failed")

        return self.async_abort(reason="no_import_data")


class PremierInnFlowHandler(config_entries.OptionsFlow):
    """PremierInn flow handler."""

    def __init__(self, config_entry) -> None:
        """Init."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Init."""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
