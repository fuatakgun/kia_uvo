"""Device Tracker for Hyundai / Kia Connect integration."""
from __future__ import annotations

import logging
from typing import Final

from hyundai_kia_connect_api import Vehicle, VehicleManager
from hyundai_kia_connect_api.Vehicle import EvChargeLimits

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)

AC_CHARGING_LIMIT_KEY = "_ac_charging_limit"
DC_CHARGING_LIMIT_KEY = "_dc_charging_limit"

CHARGING_LIMIT_DESCRIPTIONS: Final[tuple[NumberEntityDescription, ...]] = (
    NumberEntityDescription(
        key=AC_CHARGING_LIMIT_KEY,
        name="AC Charging Limit",
        icon="mdi:ev-plug-type2",
        min_value=50,
        max_value=100,
        step=10,
    ),
    NumberEntityDescription(
        key=DC_CHARGING_LIMIT_KEY,
        name="DC Charging Limit",
        icon="mdi:ev-plug-ccs2",
        min_value=50,
        max_value=100,
        step=10,
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        for descr in CHARGING_LIMIT_DESCRIPTIONS:
            entities.append(HyundaiKiaChargingLimitNumber(coordinator, descr, vehicle))

    async_add_entities(entities)
    return True


class HyundaiKiaChargingLimitNumber(NumberEntity, HyundaiKiaConnectEntity):
    _vehicle_manager: VehicleManager
    _vehicle: Vehicle

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: NumberEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        self.entity_description = description
        self._vehicle_manager = coordinator.vehicle_manager
        self._vehicle = vehicle

    @property
    def value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if self.entity_description.key == AC_CHARGING_LIMIT_KEY:
            return self._vehicle.ev_charge_limits.ac
        else:
            return self._vehicle.ev_charge_limits.dc

    async def async_set_value(self, value: float) -> None:
        """Set new charging limit."""
        # force refresh of state so that we can get the value for the other charging limit
        # since we have to set both limits as compound API call.
        current_limits = await self.hass.async_add_executor_job(
            self._vehicle_manager.api.get_charge_limits,
            self._vehicle_manager.token,
            self.vehicle,
        )

        # don't do anything for null change
        if (
            self.entity_description.key == AC_CHARGING_LIMIT_KEY
            and current_limits.ac == int(value)
        ):
            return
        if (
            self.entity_description.key == DC_CHARGING_LIMIT_KEY
            and current_limits.dc == int(value)
        ):
            return

        # set new limits
        self._vehicle.ev_charge_limits = (
            EvChargeLimits(ac=value, dc=current_limits.dc)
            if self.entity_description.key == AC_CHARGING_LIMIT_KEY
            else EvChargeLimits(ac=current_limits.ac, dc=value)
        )

        await self.hass.async_add_executor_job(
            self._vehicle_manager.api.set_charge_limits,
            self._vehicle_manager.token,
            self._vehicle,
            self._vehicle.ev_charge_limits,
        )

        self.async_write_ha_state()
