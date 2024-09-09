"""PremmierInn Coordinator."""
from datetime import timedelta
import logging
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
import aiohttp
from .const import (
    DOMAIN,
    HOST,
    CONF_ARRIVAL_DATE,
    CONF_LAST_NAME,
    CONF_RES_NO,
    FIND_BOOKING_POST_BODY,
    BOOKING_CONF_POST_BODY,
    HOTEL_INFORMATION_POST_BODY,
    REQUEST_HEADER,
    CONF_VARIABLES,
    CONF_FIND_BOOKING,
    CONF_FIND_BOOKING_CRITERIA,
    CONF_DATA,
    CONF_POST,
    CONF_BASKET_REFERENCE,
    CONF_BOOKING_CONFIRMATION,
    CONF_HOTEL_INFORMATION,
    CONF_HOTEL_ID,
    CONF_COUNTRY,
    CONF_GERMANY,
    CONF_GB,
    CONF_DE
)

_LOGGER = logging.getLogger(__name__)


def get_country(data: dict) -> str:
    if CONF_COUNTRY in data and data[CONF_COUNTRY] == CONF_GERMANY:
        return CONF_DE
    return CONF_GB


class PremierInnCoordinator(DataUpdateCoordinator):
    """Data coordinator."""

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession, data: dict) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=300),
        )
        self.session = session
        self.res_no = data[CONF_RES_NO]
        self.arrival_date = data[CONF_ARRIVAL_DATE]
        self.last_name = data[CONF_LAST_NAME]
        self.country = get_country(data)

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            body = {}
            FIND_BOOKING_POST_BODY[CONF_VARIABLES][CONF_FIND_BOOKING_CRITERIA][CONF_ARRIVAL_DATE] = self.arrival_date
            FIND_BOOKING_POST_BODY[CONF_VARIABLES][CONF_FIND_BOOKING_CRITERIA][CONF_LAST_NAME] = self.last_name
            FIND_BOOKING_POST_BODY[CONF_VARIABLES][CONF_FIND_BOOKING_CRITERIA][CONF_RES_NO] = self.res_no
            FIND_BOOKING_POST_BODY[CONF_VARIABLES][CONF_FIND_BOOKING_CRITERIA][CONF_COUNTRY] = self.country

            find_booking_resp = await self.session.request(
                method=CONF_POST,
                url=HOST,
                json=FIND_BOOKING_POST_BODY,
                headers=REQUEST_HEADER,
            )

            if find_booking_resp.status == 200:
                find_booking = await find_booking_resp.json()

                # Validate response structure
                if not isinstance(find_booking, dict):
                    raise ValueError("Unexpected response format")

                BOOKING_CONF_POST_BODY[CONF_VARIABLES][CONF_BASKET_REFERENCE] = find_booking.get(
                    CONF_DATA)[CONF_FIND_BOOKING][CONF_BASKET_REFERENCE]
                BOOKING_CONF_POST_BODY[CONF_VARIABLES][CONF_COUNTRY] = self.country

                booking_conf_resp = await self.session.request(
                    method=CONF_POST,
                    url=HOST,
                    json=BOOKING_CONF_POST_BODY,
                    headers=REQUEST_HEADER,
                )

                if booking_conf_resp.status == 200:
                    booking_conf = await booking_conf_resp.json()

                    booking_confirmation = booking_conf.get(
                        CONF_DATA)[CONF_BOOKING_CONFIRMATION]
                    body[CONF_BOOKING_CONFIRMATION] = booking_confirmation

                    HOTEL_INFORMATION_POST_BODY[CONF_VARIABLES][CONF_HOTEL_ID] = booking_confirmation[CONF_HOTEL_ID]
                    HOTEL_INFORMATION_POST_BODY[CONF_VARIABLES][CONF_COUNTRY] = self.country

                    hotel_info_resp = await self.session.request(
                        method=CONF_POST,
                        url=HOST,
                        json=HOTEL_INFORMATION_POST_BODY,
                        headers=REQUEST_HEADER,
                    )

                    if hotel_info_resp.status == 200:
                        hotel_info = await hotel_info_resp.json()

                        hotel_information = hotel_info.get(
                            CONF_DATA)[CONF_HOTEL_INFORMATION]
                        body[CONF_HOTEL_INFORMATION] = hotel_information

                return body
            else:
                raise InvalidAuth("Invalid authentication credentials")

        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except PremierInnError as err:
            raise UpdateFailed(str(err)) from err
        except ValueError as err:
            _LOGGER.exception("Value error occurred: %s", err)
            raise UpdateFailed(f"Unexpected response: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected exception: %s", err)
            raise UnknownError from err


class PremierInnError(HomeAssistantError):
    """Base error."""


class InvalidAuth(PremierInnError):
    """Raised when invalid authentication credentials are provided."""


class APIRatelimitExceeded(PremierInnError):
    """Raised when the API rate limit is exceeded."""


class UnknownError(PremierInnError):
    """Raised when an unknown error occurs."""
