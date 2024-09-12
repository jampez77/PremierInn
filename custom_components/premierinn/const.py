"""Constants for the Premier Inn integration."""

DOMAIN = "premierinn"
HOST = "https://api.premierinn.com/graphql"
CONF_ARRIVAL_DATE = "arrival_date"
CONF_ARRIVALDATE = "arrivalDate"
CONF_LAST_NAME = "last_name"
CONF_LASTNAME = "lastName"
CONF_RES_NO = "res_no"
CONF_RESNO = "resNo"
CONF_VARIABLES = "variables"
CONF_CALENDARS = "calendars"
CONF_CREATE_CALENDAR = "create_calendar"
CONF_COUNTRY = "country"
CONF_GERMANY = "Germany"
CONF_GREAT_BRITAIN = "Great Britain"
CONF_GB = "gb"
CONF_DE = "de"
CONF_FIND_BOOKING_CRITERIA = "findBookingCriteria"
CONF_FIND_BOOKING = "findBooking"
CONF_DATA = "data"
CONF_POST = "POST"
CONF_BASKET_REFERENCE = "basketReference"
CONF_BOOKING_CONFIRMATION = "bookingConfirmation"
CONF_HOTEL_INFORMATION = "hotelInformation"
CONF_HOTEL_ID = "hotelId"
CONF_ADD_BOOKING = "add_booking"
CONF_REMOVE_BOOKING = "remove_booking"

REQUEST_HEADER = {
    "User-Agent": "PostmanRuntime/7.41.2",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Accept-Language": "en-GB,en;q=0.9,en-US;q=0.8",
    "Cookie": "_abck=",
}

FIND_BOOKING_POST_BODY = {
    "query": "\nquery findBookingQuery($findBookingCriteria: FindBookingCriteria!){\n    findBooking(findBookingCriteria: $findBookingCriteria){\n     cookieName\n      token\n      minutesTillExpiry\n      basketReference\n    }\n  }\n",
    CONF_VARIABLES: {
        CONF_FIND_BOOKING_CRITERIA: {
            "arrivalDate": "{arrivalDate}",
            "lastName": "{lastName}",
            "resNo": "{resNo}",
            "country": "{country}",
            "language": "en",
        }
    },
}

BOOKING_CONF_POST_BODY = {
    "query": "\n  query bookingConfirmation(\n    $basketReference: String!\n    $language: String!\n    $country: String!\n    $bookingChannel: String\n  ) {\n    bookingConfirmation(\n      basketReference: $basketReference\n      language: $language\n      country: $country\n      bookingChannel: $bookingChannel\n    ) {\n      reservationByIdList {\n        reservationId\n        reservationGuestList {\n          givenName\n          surName\n        }\n       roomStay {\n          checkInTime\n          checkOutTime\n          ratePlanCode\n          arrivalDate\n          departureDate\n          bookingChannel\n          roomPrice\n          cot\n          adultsNumber\n          roomExtraInfo {\n            roomName\n          }\n          childrenNumber\n        }\n        reservationOverrideReasons {\n          reasonCode\n          callerName\n          managerName\n          reasonName\n        }\n        reservationOverridden\n        guaranteeCode\n        reservationStatus\n        additionalGuestInfo {\n          purposeOfStay\n        }\n      }\n      balanceOutstanding\n      currencyCode\n      newTotal\n      policyCode\n      previousTotal\n      totalCost\n      hotelId\n      hotelName\n     rateMessage\n      bookingReference\n      basketReference\n    }\n  }\n",
    CONF_VARIABLES: {
        "basketReference": "{basketReference}",
        "language": "en",
        "country": "{country}",
        "bookingChannel": "PI",
    },
    "operationName": "bookingConfirmation",
}

HOTEL_INFORMATION_POST_BODY = {
    "query": "\n  query GetHotelInformation($hotelId: String!, $country: String!, $language: String!) {\n    hotelInformation(hotelId: $hotelId, country: $country, language: $language) {\n      address {\n        addressLine1\n        addressLine2\n        addressLine3\n        addressLine4\n        postalCode\n        country\n      }\n      hotelId\n      hotelOpeningDate\n      name\n      brand\n      parkingDescription\n      directions\n      county\n      contactDetails {\n        phone\n        hotelNationalPhone\n        email\n      }\n      coordinates {\n        latitude\n        longitude\n      }\n      importantInfo {\n        title\n        infoItems {\n          text\n          priority\n          startDate\n          endDate\n        }\n      }\n    }\n  }\n",
    CONF_VARIABLES: {"hotelId": "{hotelId}", "language": "en", "country": "{country}"},
    "operationName": "GetHotelInformation",
}
