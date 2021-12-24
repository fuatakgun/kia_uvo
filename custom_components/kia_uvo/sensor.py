import logging

from homeassistant.const import (
    PERCENTAGE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_TEMPERATURE,
    TIME_MINUTES,
    TEMP_FAHRENHEIT,
    TEMP_CELSIUS,
)
from homeassistant.util import distance as distance_util
import homeassistant.util.dt as dt_util
from .Vehicle import Vehicle
from .KiaUvoEntity import KiaUvoEntity
from .const import (
    DYNAMIC_TEMP_UNIT,
    REGION_USA,
    REGIONS,
    DOMAIN,
    DATA_VEHICLE_INSTANCE,
    NOT_APPLICABLE,
    DISTANCE_UNITS,
    VEHICLE_ENGINE_TYPE,
    DYNAMIC_DISTANCE_UNIT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    vehicle: Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]

    INSTRUMENTS = []

    if (
        vehicle.engine_type is VEHICLE_ENGINE_TYPE.EV
        or vehicle.engine_type is VEHICLE_ENGINE_TYPE.PHEV
    ):
        INSTRUMENTS.append(
            (
                "evBatteryPercentage",
                "EV Battery",
                "vehicleStatus.evStatus.batteryStatus",
                PERCENTAGE,
                "mdi:car-electric",
                DEVICE_CLASS_BATTERY,
            )
        )
        INSTRUMENTS.append(
            (
                "evDrivingDistance",
                "Range by EV",
                "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.evModeRange.value",
                DYNAMIC_DISTANCE_UNIT,
                "mdi:road-variant",
                None,
            )
        )
        INSTRUMENTS.append(
            (
                "totalDrivingDistance",
                "Range Total",
                "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.totalAvailableRange.value",
                DYNAMIC_DISTANCE_UNIT,
                "mdi:road-variant",
                None,
            )
        )
        INSTRUMENTS.append(
            (
                "estimatedCurrentChargeDuration",
                "Estimated Current Charge Duration",
                "vehicleStatus.evStatus.remainTime2.atc.value",
                TIME_MINUTES,
                "mdi:ev-station",
                None,
            )
        )
        INSTRUMENTS.append(
            (
                "estimatedFastChargeDuration",
                "Estimated Fast Charge Duration",
                "vehicleStatus.evStatus.remainTime2.etc1.value",
                TIME_MINUTES,
                "mdi:ev-station",
                None,
            )
        )
        INSTRUMENTS.append(
            (
                "estimatedPortableChargeDuration",
                "Estimated Portable Charge Duration",
                "vehicleStatus.evStatus.remainTime2.etc2.value",
                TIME_MINUTES,
                "mdi:ev-station",
                None,
            )
        )
        INSTRUMENTS.append(
            (
                "estimatedStationChargeDuration",
                "Estimated Station Charge Duration",
                "vehicleStatus.evStatus.remainTime2.etc3.value",
                TIME_MINUTES,
                "mdi:ev-station",
                None,
            )
        )
        INSTRUMENTS.append(
            (
                "targetSOCACCapacity",
                "Target Capacity of Charge AC",
                "vehicleStatus.evStatus.targetSOC.1.targetSOClevel",
                PERCENTAGE,
                "mdi:car-electric",
                None,
            )
        )
        INSTRUMENTS.append(
            (
                "targetSOCDCCapacity",
                "Target Capacity of Charge DC",
                "vehicleStatus.evStatus.targetSOC.0.targetSOClevel",
                PERCENTAGE,
                "mdi:car-electric",
                None,
            )
        )

        if vehicle.kia_uvo_api.supports_soc_range:
            INSTRUMENTS.append(
                (
                    "targetSOCACRange",
                    "Target Range of Charge AC",
                    "vehicleStatus.evStatus.targetSOC.1.dte.rangeByFuel.totalAvailableRange.value",
                    DYNAMIC_DISTANCE_UNIT,
                    "mdi:ev-station",
                    None,
                )
            )
            INSTRUMENTS.append(
                (
                    "targetSOCDCRange",
                    "Target Range of Charge DC",
                    "vehicleStatus.evStatus.targetSOC.0.dte.rangeByFuel.totalAvailableRange.value",
                    DYNAMIC_DISTANCE_UNIT,
                    "mdi:ev-station",
                    None,
                )
            )

    if vehicle.engine_type is VEHICLE_ENGINE_TYPE.PHEV:
        INSTRUMENTS.append(
            (
                "fuelDrivingDistance",
                "Range by Fuel",
                "vehicleStatus.evStatus.drvDistance.0.rangeByFuel.gasModeRange.value",
                DYNAMIC_DISTANCE_UNIT,
                "mdi:road-variant",
                None,
            )
        )
    if vehicle.engine_type is VEHICLE_ENGINE_TYPE.IC:
        INSTRUMENTS.append(
            (
                "fuelDrivingDistance",
                "Range by Fuel",
                "vehicleStatus.dte.value",
                DYNAMIC_DISTANCE_UNIT,
                "mdi:road-variant",
                None,
            )
        )

    INSTRUMENTS.append(
        (
            "odometer",
            "Odometer",
            "odometer.value",
            DYNAMIC_DISTANCE_UNIT,
            "mdi:speedometer",
            None,
        )
    )
    INSTRUMENTS.append(
        (
            "lastService",
            "Last Service",
            "lastService.value",
            DYNAMIC_DISTANCE_UNIT,
            "mdi:car-wrench",
            None,
        )
    )
    INSTRUMENTS.append(
        (
            "nextService",
            "Next Service",
            "nextService.value",
            DYNAMIC_DISTANCE_UNIT,
            "mdi:car-wrench",
            None,
        )
    )
    INSTRUMENTS.append(
        (
            "geocodedLocation",
            "Geocoded Location",
            "vehicleLocation.geocodedLocation.display_name",
            None,
            "mdi:map",
            None,
        )
    )
    INSTRUMENTS.append(
        (
            "carBattery",
            "Car Battery",
            "vehicleStatus.battery.batSoc",
            PERCENTAGE,
            "mdi:car-battery",
            DEVICE_CLASS_BATTERY,
        )
    )
    INSTRUMENTS.append(
        (
            "temperatureSetpoint",
            "Set Temperature",
            "vehicleStatus.airTemp.value",
            DYNAMIC_TEMP_UNIT,
            None,
            DEVICE_CLASS_TEMPERATURE,
        )
    )

    sensors = []

    for id, description, key, unit, icon, device_class in INSTRUMENTS:
        if vehicle.get_child_value(key) is None:
            _LOGGER.debug(f"skipping sensor for missing data, key:{key}")
        else:
            sensors.append(
                InstrumentSensor(
                    hass,
                    config_entry,
                    vehicle,
                    id,
                    description,
                    key,
                    unit,
                    icon,
                    device_class,
                )
            )

    sensors.append(
        InstrumentSensor(
            hass,
            config_entry,
            vehicle,
            "lastUpdated",
            "Last Update",
            "last_updated",
            "None",
            "mdi:update",
            DEVICE_CLASS_TIMESTAMP,
        )
    )
    async_add_entities(sensors, True)


class InstrumentSensor(KiaUvoEntity):
    def __init__(
        self,
        hass,
        config_entry,
        vehicle: Vehicle,
        id,
        description,
        key,
        unit,
        icon,
        device_class,
    ):
        super().__init__(hass, config_entry, vehicle)
        self._id = id
        self._description = description
        self._key = key
        self._unit = unit
        self._source_unit = unit
        self._icon = icon
        self._device_class = device_class
        self._dynamic_distance_unit = False
        if self._unit == DYNAMIC_DISTANCE_UNIT:
            self._dynamic_distance_unit = True

    @property
    def state(self):
        if self._id.startswith("targetSOC"):
            self.vehicle.get_child_value("vehicleStatus.evStatus.targetSOC").sort(
                key=lambda x: x["plugType"]
            )
        if self._id == "lastUpdated":
            return dt_util.as_local(self.vehicle.last_updated).isoformat()

        value = self.vehicle.get_child_value(self._key)

        if value is None:
            value = NOT_APPLICABLE
        else:
            if self._source_unit != self._unit:
                value = distance_util.convert(
                    float(value), self._source_unit, self._unit
                )
            if isinstance(value, float) == True:
                value = round(value, 1)

        return value

    @property
    def unit_of_measurement(self):
        if self._unit == DYNAMIC_TEMP_UNIT:
            if REGIONS[self.vehicle.kia_uvo_api.region] != REGION_USA:
                return TEMP_CELSIUS
            else:
                return TEMP_FAHRENHEIT

        if self._dynamic_distance_unit == False:
            return self._unit

        key_unit = self._key.replace(".value", ".unit")
        found_unit = self.vehicle.get_child_value(key_unit)
        if found_unit in DISTANCE_UNITS:
            self._unit = self.vehicle.unit_of_measurement
            self._source_unit = DISTANCE_UNITS[found_unit]
        else:
            self._unit = NOT_APPLICABLE
            self._source_unit = NOT_APPLICABLE

        return self._unit

    @property
    def state_attributes(self):
        if self._id == "geocodedLocation":
            return {
                "address": self.vehicle.get_child_value(
                    "vehicleLocation.geocodedLocation.address"
                )
            }
        return None

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        return self._device_class

    @property
    def name(self):
        return f"{self.vehicle.name} {self._description}"

    @property
    def unique_id(self):
        return f"{DOMAIN}-{self._id}-{self.vehicle.id}"
