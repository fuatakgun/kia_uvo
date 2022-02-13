import logging
from typing import Any, cast


from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import ServiceCall, callback, HomeAssistant
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from homeassistant.helpers import device_registry
from hyundai_kia_connect_api import ClimateRequestOptions

from .const import DOMAIN

SERVICE_UPDATE = "update"
SERVICE_FORCE_UPDATE = "force_update"
SERVICE_LOCK = "lock"
SERVICE_UNLOCK = "unlock"
SERVICE_STOP_CLIMATE = "stop_climate"
SERVICE_START_CLIMATE = "start_climate"
SERVICE_START_CHARGE = "start_charge"
SERVICE_STOP_CHARGE = "stop_charge"
SERVICE_SET_CHARGE_LIMIT = "set_charge_limits"

SUPPORTED_SERVICES = (
    SERVICE_UPDATE,
    SERVICE_FORCE_UPDATE,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    SERVICE_STOP_CLIMATE,
    SERVICE_START_CLIMATE,
    SERVICE_START_CHARGE,
    SERVICE_STOP_CHARGE,
    SERVICE_SET_CHARGE_LIMIT,
)

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_services(hass: HomeAssistant) -> bool:
    """Set up services for Hyundai Kia Connect"""

    async def async_handle_force_update(call):
        coordinator = _get_coordinator_from_device(hass, call)
        await coordinator.async_force_update_all()

    async def async_handle_update(call):
        _LOGGER.debug(f"Call:{call.data}")
        coordinator = _get_coordinator_from_device(hass, call)
        await coordinator.async_update_all()

    async def async_handle_start_climate(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        if not call.data.get("flseatheat") and not call.data.get("flseatcool"):
            front_left_seat_status = 0
        elif call.data.get("flseatheat"):
            if call.data.get("flseatheatlevel"):
                if call.data.get("flseatheatlevel") == 1:
                    front_left_seat_status = 6
                elif call.data.get("flseatheatlevel") == 2:
                    front_left_seat_status = 7
                elif call.data.get("flseatheatlevel") == 3:
                    front_left_seat_status = 8
            else:
                front_left_seat_status = 1
        elif call.data.get("flseatcool"):
            if call.data.get("flseatcoollevel"):
                if call.data.get("flseatcoollevel") == 1:
                    front_left_seat_status = 3
                elif call.data.get("flseatcoollevel") == 2:
                    front_left_seat_status = 4
                elif call.data.get("flseatcoollevel") == 3:
                    front_left_seat_status = 5
            else:
                front_left_seat_status = 1
        if call.data.get("flseatcool") and call.data.get("flseatheat"):
            #Throw exception. Not possible.
            pass
        climate_request_options = ClimateRequestOptions(
            set_temp=call.data.get("temperature"),
            duration=call.data.get("duration"),
            climate=call.data.get("climate"),
            heating=call.data.get("heating"),
            front_left_seat=front_left_seat_status,
        )
        await coordinator.async_start_climate(vehicle_id, climate_request_options)

    async def async_handle_stop_climate(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_stop_climate(vehicle_id)

    async def async_handle_lock(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_lock_vehicle(vehicle_id)

    async def async_handle_unlock(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)

        await coordinator.async_unlock_vehicle(vehicle_id)

    async def async_handle_start_charge(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_start_charge(vehicle_id)

    async def async_handle_stop_charge(call):
        coordinator = _get_coordinator_from_device(hass, call)
        vehicle_id = _get_vehicle_id_from_device(hass, call)
        await coordinator.async_stop_charge(vehicle_id)

    async def async_handle_set_charge_limit(call):
        coordinator = _get_coordinator_from_device(hass, call)
        ac_limit = call.data.get("ac_limit")
        dc_limit = call.data.get("dc_limit")
        await coordinator.set_charge_limits(
            call.data[ATTR_DEVICE_ID], ac_limit, dc_limit
        )

    services = {
        SERVICE_FORCE_UPDATE: async_handle_force_update,
        SERVICE_UPDATE: async_handle_update,
        SERVICE_START_CLIMATE: async_handle_start_climate,
        SERVICE_STOP_CLIMATE: async_handle_stop_climate,
        SERVICE_LOCK: async_handle_lock,
        SERVICE_UNLOCK: async_handle_unlock,
        SERVICE_START_CHARGE: async_handle_start_charge,
        SERVICE_STOP_CHARGE: async_handle_stop_charge,
        SERVICE_SET_CHARGE_LIMIT: async_handle_set_charge_limit,
    }

    for service in SUPPORTED_SERVICES:
        hass.services.async_register(DOMAIN, service, services[service])
    return True


@callback
def async_unload_services(hass) -> None:
    for service in SUPPORTED_SERVICES:
        hass.services.async_remove(DOMAIN, service)


def _get_vehicle_id_from_device(hass: HomeAssistant, call: ServiceCall) -> str:
    device_entry = device_registry.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
    for entry in device_entry.identifiers:
        if entry[0] == DOMAIN:
            vehicle_id = entry[1]
    return vehicle_id


def _get_coordinator_from_device(
    hass: HomeAssistant, call: ServiceCall
) -> HyundaiKiaConnectDataUpdateCoordinator:
    device_entry = device_registry.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
    config_entry_ids = device_entry.config_entries
    config_entry_id = next(
        (
            config_entry_id
            for config_entry_id in config_entry_ids
            if cast(
                ConfigEntry,
                hass.config_entries.async_get_entry(config_entry_id),
            ).domain
            == DOMAIN
        ),
        None,
    )
    config_entry_unique_id = hass.config_entries.async_get_entry(
        config_entry_id
    ).unique_id
    return hass.data[DOMAIN][config_entry_unique_id]
