"""Sensors for Solid GPS."""
from __future__ import annotations

import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolidGPSCoordinator

# DeviceStatus values observed from the dashboard frontend
DEVICE_STATUS_MAP = {
    0: "Sleeping till Movement",
    1: "Active",
    2: "Moving",
    3: "Parked",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SolidGPSCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for imei in coordinator.data:
        entities += [
            SolidGPSBatterySensor(coordinator, imei),
            SolidGPSStatusSensor(coordinator, imei),
            SolidGPSLastUpdateSensor(coordinator, imei),
            SolidGPSNextUpdateSensor(coordinator, imei),
            SolidGPSDistanceSensor(coordinator, imei),
            SolidGPSDistanceKmSensor(coordinator, imei),
        ]
    async_add_entities(entities)


class _SolidGPSBaseSensor(CoordinatorEntity[SolidGPSCoordinator], SensorEntity):
    """Shared base for all Solid GPS sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolidGPSCoordinator, imei: str) -> None:
        super().__init__(coordinator)
        self._imei = imei

    @property
    def device_info(self):
        info = self.coordinator.data[self._imei]["device_info"]
        return {
            "identifiers": {(DOMAIN, self._imei)},
            "name": info.get("nickname", self._imei),
            "manufacturer": "Solid GPS",
            "model": info.get("deviceType"),
        }

    def _info(self):
        return self.coordinator.data[self._imei]["device_info"]


class SolidGPSBatterySensor(_SolidGPSBaseSensor):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Battery"

    def __init__(self, coordinator, imei):
        super().__init__(coordinator, imei)
        self._attr_unique_id = f"{imei}_battery"

    @property
    def native_value(self) -> int | None:
        info = self._info()
        live_fix = info.get("live_fix") or {}
        return live_fix.get("bat_status", info.get("batteryStatus"))


class SolidGPSStatusSensor(_SolidGPSBaseSensor):
    _attr_name = "Status"
    _attr_icon = "mdi:map-marker-check"

    def __init__(self, coordinator, imei):
        super().__init__(coordinator, imei)
        self._attr_unique_id = f"{imei}_status"

    @property
    def native_value(self) -> str:
        info = self._info()
        live_fix = info.get("live_fix") or {}
        raw = live_fix.get("dev_status", info.get("deviceStatus", 0))
        return DEVICE_STATUS_MAP.get(raw, f"Unknown ({raw})")


class SolidGPSLastUpdateSensor(_SolidGPSBaseSensor):
    _attr_name = "Last Update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, imei):
        super().__init__(coordinator, imei)
        self._attr_unique_id = f"{imei}_last_update"

    @property
    def native_value(self) -> datetime.datetime | None:
        info = self._info()
        live_fix = info.get("live_fix") or {}
        epoch_ms = live_fix.get("utc") or info.get("lastUpdateUTC")
        if not epoch_ms:
            return None
        return datetime.datetime.fromtimestamp(epoch_ms / 1000, tz=datetime.timezone.utc)


class SolidGPSNextUpdateSensor(_SolidGPSBaseSensor):
    _attr_name = "Next Update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, imei):
        super().__init__(coordinator, imei)
        self._attr_unique_id = f"{imei}_next_update"

    @property
    def native_value(self) -> datetime.datetime | None:
        info = self._info()
        live_fix = info.get("live_fix") or {}
        epoch_ms = live_fix.get("next_update") or info.get("nextExpectedUTC")
        if not epoch_ms:
            return None
        return datetime.datetime.fromtimestamp(epoch_ms / 1000, tz=datetime.timezone.utc)


class SolidGPSDistanceSensor(_SolidGPSBaseSensor):
    _attr_name = "Lifetime Distance"
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:map-marker-distance"

    def __init__(self, coordinator, imei):
        super().__init__(coordinator, imei)
        self._attr_unique_id = f"{imei}_distance"

    @property
    def native_value(self) -> int | None:
        return self._info().get("distanceTravelled")


class SolidGPSDistanceKmSensor(_SolidGPSBaseSensor):
    _attr_name = "Lifetime Distance (km)"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:map-marker-distance"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, imei):
        super().__init__(coordinator, imei)
        self._attr_unique_id = f"{imei}_distance_km"

    @property
    def native_value(self) -> float | None:
        metres = self._info().get("distanceTravelled")
        if metres is None:
            return None
        return round(metres / 1000, 2)

