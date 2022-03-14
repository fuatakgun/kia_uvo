"""Switches for Hyundai / Kia Connect integration."""
from __future__ import annotations

import logging
from time import sleep

from hyundai_kia_connect_api import ClimateRequestOptions, Vehicle, VehicleManager
from hyundai_kia_connect_api.utils import get_hex_temp_into_index

from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary_sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        async_add_entities([HyundaiKiaCarClimateControlSwitch(coordinator, vehicle)])


class HyundaiKiaCarClimateControlSwitch(HyundaiKiaConnectEntity, ClimateEntity):
    """Hyundai / Kia Connect Car Climate Control."""

    vehicle_manager: VehicleManager
    vehicle: Vehicle

    # The python lib climate request is also treated as
    # internal target state that can be sent to the car
    climate_config: ClimateRequestOptions

    # TODO: if possible in Climate, add possibility to set those
    # as well. Are there maybe additional properties?
    heat_status_int_to_str: dict[int | None, str | None] = {
        None: None,
        0: "Off",
        1: "Steering Wheel and Rear Window",
        2: "Rear Window",
        3: "Steering Wheel",
    }
    heat_status_str_to_int = {v: k for [k, v] in heat_status_int_to_str.items()}

    def get_internal_heat_int_for_climate_request(self):
        if (
            self.vehicle.steering_wheel_heater_is_on
            and self.vehicle.back_window_heater_is_on
        ):
            return 1
        elif self.vehicle.back_window_heater_is_on:
            return 2
        elif self.vehicle.steering_wheel_heater_is_on:
            return 3
        else:
            return 0

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the Climate Control."""
        super().__init__(coordinator, vehicle)
        self.entity_description = ClimateEntityDescription(
            key="climate_control",
            icon="mdi:air-conditioner",
            name="Climate Control",
            unit_of_measurement=vehicle._air_temperature_unit,
        )
        self.vehicle_manager = coordinator.vehicle_manager
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_climate_control"
        self._attr_name = f"{vehicle.name} Climate Control"

        # set the Climate Request to the current actual state of the car
        self.climate_config = ClimateRequestOptions(
            set_temp=self.vehicle_manager.api.temperature_range[
                get_hex_temp_into_index(self.vehicle._air_temperature)
            ],
            climate=self.vehicle.air_control_is_on,
            heating=self.get_internal_heat_int_for_climate_request(),
            defrost=self.vehicle.defrost_is_on,
        )

    @property
    def temperature_unit(self) -> str:
        """Get the Cars Climate Control Temperature Unit."""
        return self.vehicle._air_temperature_unit

    @property
    def current_temperature(self) -> float | None:
        """Get the current in-car temperature."""
        index = get_hex_temp_into_index(self.vehicle.air_temperature)
        return self.vehicle_manager.api.temperature_range[index]

    @property
    def target_temperature(self) -> float | None:
        """Get the desired in-car target temperature."""
        # TODO: use Coordinator data, not internal state
        return self.climate_config.set_temp

    @property
    def target_temperature_step(self) -> float | None:
        """Get the step size for adjusting the in-car target temperature."""
        # TODO: get from lib
        return 0.5

    # TODO: unknown
    @property
    def min_temp(self) -> float:
        """Get the minimum settable temperature."""
        # TODO: get from lib
        return 14

    # TODO: unknown
    @property
    def max_temp(self) -> float:
        """Get the maximum settable temperature."""
        # TODO: get from lib
        return 30

    @property
    def hvac_mode(self) -> str:
        """Get the configured climate control operation mode."""

        if not self.vehicle.air_control_is_on:
            return HVAC_MODE_OFF

        # Cheating: there is no perfect mapping to either heat or cool,
        # as the API can only set target temp and then decides: so we
        # just derive the same by temperatur change direction.
        if self.current_temperature > self.climate_config.set_temp:
            return HVAC_MODE_COOL
        if self.current_temperature < self.climate_config.set_temp:
            return HVAC_MODE_HEAT

        # TODO: what could be a sensible answer if target temp is reached?
        return HVAC_MODE_AUTO

    @property
    def hvac_action(self) -> str | None:
        # TODO: use Coordinator data, not internal state
        """
        Get what the in-car climate control is currently doing.

        Computed value based on current and desired temp and configured operation mode.
        """
        if not self.vehicle.air_control_is_on:
            return CURRENT_HVAC_OFF

        # if temp is lower than target, it HEATs
        if self.current_temperature < self.climate_config.set_temp:
            return CURRENT_HVAC_HEAT

        # if temp is higher than target, it COOLs
        if self.current_temperature > self.climate_config.set_temp:
            return CURRENT_HVAC_COOL

        # target temp reached
        if self.current_temperature == self.climate_config.set_temp:
            return CURRENT_HVAC_IDLE

        # should not happen, fallback
        return CURRENT_HVAC_OFF

    @property
    def hvac_modes(self) -> list[str]:
        """Supported in-car climate control modes."""
        return [
            HVAC_MODE_OFF,
            # if only heater is activated
            HVAC_MODE_HEAT,
            # if only AC is activated
            HVAC_MODE_COOL,
        ]

    @property
    def supported_features(self) -> int:
        """Supported in-car climate control features."""
        return SUPPORT_TARGET_TEMPERATURE

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the operation mode of the in-car climate control."""

        if hvac_mode == HVAC_MODE_OFF:
            await self.hass.async_add_executor_job(
                self.vehicle_manager.api.stop_climate,
                self.vehicle_manager.token,
                self.vehicle,
            )
            self.vehicle.air_control_is_on = False
        else:
            await self.hass.async_add_executor_job(
                self.vehicle_manager.api.start_climate,
                self.vehicle_manager.token,
                self.vehicle,
                self.climate_config,
            )
            self.vehicle.air_control_is_on = True
        self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set the desired in-car temperature. Does not turn on the AC."""
        old_temp = self.climate_config.set_temp
        self.climate_config.set_temp = kwargs.get(ATTR_TEMPERATURE)

        # activation is controlled separately, but if system is turned on
        # and temp has changed, send update to car
        if self.hvac_mode != HVAC_MODE_OFF and old_temp != self.climate_config.set_temp:
            # Car does not accept changing the temp after starting the heating. So we have to turn off first
            await self.hass.async_add_executor_job(
                self.vehicle_manager.api.stop_climate,
                self.vehicle_manager.token,
                self.vehicle,
            )
            # Wait, because the car ignores the start_climate command if it comes too fast after stopping
            # TODO: replace with some more event driven method
            await self.hass.async_add_executor_job(sleep, 5.0)
            await self.hass.async_add_executor_job(
                self.vehicle_manager.api.start_climate,
                self.vehicle_manager.token,
                self.vehicle,
                self.climate_config,
            )
        self.coordinator.async_request_refresh()
        self.async_write_ha_state()
