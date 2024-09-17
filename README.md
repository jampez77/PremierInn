# ![Logo](https://github.com/jampez77/PremierInn/blob/main/logo.png "Premier Inn Logo") Premier Inn bookings for Home Assistant

This component provides details of a specified Premier Inn booking and adds sensors to [Home Assistant](https://www.home-assistant.io/) which can be used in your own automations.

---

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE.md)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
![Project Maintenance][maintenance-shield]


Enjoying this? Help me out with a :beers: or :coffee:!

[![coffee](https://www.buymeacoffee.com/assets/img/custom_images/black_img.png)](https://www.buymeacoffee.com/whenitworks)


## Installation through [HACS](https://hacs.xyz/)

There is an active [PR](https://github.com/hacs/default/pull/2719) to get this into [HACS](https://hacs.xyz/), once that is merged then you can install the **Premier Inn** integration by searching for it there in HA instance.

Until then you will have to add this repository manually:

Go to HACS -> 3 dot menu -> Custom Repositories:- 

Paste `https://github.com/jampez77/PremierInn` into Repository field and select `Integration`

Now you should be able to find it in HACS as normal.

You can install the **Premier Inn** integration by searching for it there in HA instance.

## Manual Installation
Use this route only if you do not want to use [HACS](https://hacs.xyz/) and love the pain of manually installing regular updates.
* Add the `premierinn` folder in your `custom_components` folder

## Usage

Each entry requires a `booking reference`, `arrival date`, `surname` and the `country` that the hotel is located in. This information can be found on your booking email confirmation. Additionaly you can select an existing calendar and\or ask the integration to create a new one to display date based information such as check in/out times.

## Contributing

Contirbutions are welcome from everyone! By contributing to this project, you help improve it and make it more useful for the community. Here's how you can get involved:

### How to Contribute

1. **Report Bugs**: If you encounter a bug, please open an issue with details about the problem and how to reproduce it.
2. **Suggest Features**: Have an idea for a new feature? I'd love to hear about it! Please open an issue to discuss it.
3. **Submit Pull Requests**: If you'd like to contribute code:
   - Fork the repository and create your branch from `main`.
   - Make your changes in the new branch.
   - Open a pull request with a clear description of what you’ve done.

---
## Data 
The integration will add calendar entities for check in / out times plus a longer one for the duration of the stay. The duration entity will contain booking and hotel information within the description. 

A booking will automatically be removed when check out time arrives. The will remove all assocaited entities but NOT events added to calendars.

There should also be a geo location entity created for the hotel itself, this will put the hotel on your map in HA. It will contain the relevat hotel information as attributes.

- Hotel Information
	* Postal Address
	* Name
	* Parking Information
	* Directions
	* Contact Details
	* GPS location
- Booking Information
	* Check in / out times
	* Arrival / Departue dates
	* Room Name
	* Outstanding Balance
	* Currency Code
	* Booking Reference
	* Number and details of guests
	* Reservation Status


---

[commits-shield]: https://img.shields.io/github/commit-activity/y/jampez77/PremierInn.svg?style=for-the-badge
[commits]: https://github.com/jampez77/PremierInn/commits/main
[license-shield]: https://img.shields.io/github/license/jampez77/PremierInn.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/Maintainer-Jamie%20Nandhra--Pezone-blue
[releases-shield]: https://img.shields.io/github/v/release/jampez77/PremierInn.svg?style=for-the-badge
[releases]: https://github.com/jampez77/PremierInn/releases 
