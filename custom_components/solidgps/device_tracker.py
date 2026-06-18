"""Device tracker for Solid GPS."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolidGPSCoordinator


def _latest_gps_point(tracking: dict, imei: str) -> dict | None:
    """Return the GPS point with the highest utc value for a device."""
    try:
        gps_data = tracking["data"]["devices"][imei]["gps_data"]
        if gps_data:
            return max(gps_data, key=lambda p: p.get("utc", 0))
    except (KeyError, TypeError):
        pass
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SolidGPSCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SolidGPSTracker(coordinator, imei) for imei in coordinator.data
    )


class SolidGPSTracker(CoordinatorEntity[SolidGPSCoordinator], TrackerEntity):
    """Represent a GPS device as a device_tracker entity.

    Entity ID will be device_tracker.<IMEI>.
    """

    _attr_has_entity_name = False

    def __init__(self, coordinator: SolidGPSCoordinator, imei: str) -> None:
        super().__init__(coordinator)
        self._imei = imei
        self._attr_unique_id = imei
        self._attr_name = imei  # → entity_id: device_tracker.<imei>

    @property
    def device_info(self):
        info = self.coordinator.data[self._imei]["device_info"]
        return {
            "identifiers": {(DOMAIN, self._imei)},
            "name": info.get("nickname", self._imei),
            "manufacturer": "Solid GPS",
            "model": info.get("device_type"),
        }

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    def _gps(self) -> dict | None:
        return _latest_gps_point(self.coordinator.data[self._imei]["tracking"], self._imei)

    @property
    def latitude(self) -> float | None:
        point = self._gps()
        return float(point["latitude"]) if point else None

    @property
    def longitude(self) -> float | None:
        point = self._gps()
        return float(point["longitude"]) if point else None

    @property
    def battery_level(self) -> int | None:
        return self.coordinator.data[self._imei]["device_info"].get("bat_status")

    @property
    def extra_state_attributes(self) -> dict:
        tracking = self.coordinator.data[self._imei]["tracking"]
        point = self._gps()

        attrs = {}

        # Top-level response epoch window
        if isinstance(tracking, dict) and tracking.get("success"):
            data_block = tracking.get("data", {})
            for key in ("start_epoch", "end_epoch"):
                if key in data_block:
                    attrs[key] = data_block[key]

        # Device-level fields from tracking
        device_info = self.coordinator.data[self._imei]["device_info"]
        for key in ("active_subscription", "color", "letter_index", "device_type"):
            if key in device_info:
                attrs[key] = device_info[key]
        gps_list = device_info.get("gps_data", [])
        attrs["gps_history_points"] = len(gps_list)

        # Latest GPS point fields
        if point:
            attrs["speed_over_ground"] = point.get("sog")
            attrs["course_over_ground"] = point.get("cog")
            attrs["gps_utc"] = point.get("utc")
            attrs["gps_quality"] = point.get("quality")
            attrs["row_index"] = point.get("row_index")

        return attrs

