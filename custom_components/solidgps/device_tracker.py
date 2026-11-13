"""Device tracker for Solid GPS."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolidGPSCoordinator
from .zones import predict_location


def _latest_point_and_source(device_info: dict, tracking: dict, imei: str) -> tuple[dict | None, str | None]:
    """Return the newest known location (by utc) and which source it came from.

    Candidates are the live refresh-endpoint fix, the history endpoint's
    gps_data, and cell_data (cell-tower triangulation). The newest timestamp
    wins, so a stale cell fix never overrides a more recent GPS fix.
    """
    candidates: list[tuple[str, dict]] = []
    live_fix = device_info.get("live_fix")
    if live_fix:
        candidates.append(("refresh", live_fix))
    try:
        device = tracking["data"]["devices"][imei]
        candidates += [("history_gps", p) for p in device.get("gps_data") or []]
        candidates += [("history_cell", p) for p in device.get("cell_data") or []]
    except (KeyError, TypeError):
        pass
    if not candidates:
        return None, None
    source, point = max(candidates, key=lambda c: c[1].get("utc", 0))
    return point, source


def _latest_gps_point(device_info: dict, tracking: dict, imei: str) -> dict | None:
    """Return the freshest known location point for a device."""
    return _latest_point_and_source(device_info, tracking, imei)[0]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SolidGPSCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for imei in coordinator.data:
        entities += [
            SolidGPSTracker(coordinator, imei),
            SolidGPSPredictedTracker(coordinator, imei),
        ]
    async_add_entities(entities)


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
            "model": info.get("deviceType"),
        }

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    def _gps(self) -> dict | None:
        entry = self.coordinator.data[self._imei]
        return _latest_gps_point(entry["device_info"], entry["tracking"], self._imei)

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
        info = self.coordinator.data[self._imei]["device_info"]
        live_fix = info.get("live_fix") or {}
        return live_fix.get("bat_status", info.get("batteryStatus"))

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
        for key in ("activeSubscription", "color", "deviceType"):
            if key in device_info:
                attrs[key] = device_info[key]
        gps_list = device_info.get("gps_data") or []
        attrs["gps_history_points"] = len(gps_list)
        _, source = _latest_point_and_source(device_info, tracking, self._imei)
        attrs["location_source"] = source
        attrs["using_live_fix"] = source == "refresh"
        attrs["using_cell_location"] = source == "history_cell"

        # Latest GPS point fields
        if point:
            attrs["speed_over_ground"] = point.get("sog")
            attrs["course_over_ground"] = point.get("cog")
            attrs["gps_utc"] = point.get("utc")
            attrs["gps_quality"] = point.get("quality")
            attrs["row_index"] = point.get("row_index")

        return attrs



class SolidGPSPredictedTracker(SolidGPSTracker):
    """Best-guess location: the real fix when it is the newest, else a predicted one.

    When the newest report is a cell-tower fix, its predicted zones are reduced
    to the main cluster (outliers dropped) and the centroid is used, with
    location_accuracy covering the cluster's extent. With no usable zones the
    cell fix itself is used.

    Entity ID will be device_tracker.<IMEI>_predicted.
    """

    def __init__(self, coordinator: SolidGPSCoordinator, imei: str) -> None:
        super().__init__(coordinator, imei)
        self._attr_unique_id = f"{imei}_predicted"
        self._attr_name = f"{imei} predicted"  # → device_tracker.<imei>_predicted

    def _resolve(self) -> tuple[dict | None, str | None, dict | None]:
        """Return (point, source, prediction). prediction is set only when zones were used."""
        entry = self.coordinator.data[self._imei]
        point, source = _latest_point_and_source(
            entry["device_info"], entry["tracking"], self._imei
        )
        if point is None or source != "history_cell":
            return point, source, None
        zones = (point.get("zones") or {}).get("zones") or []
        prediction = predict_location(zones)
        if prediction is None:
            return point, source, None
        return {**point, **prediction}, "predicted_zone", prediction

    def _gps(self) -> dict | None:
        return self._resolve()[0]

    @property
    def location_accuracy(self) -> float:
        point, source, prediction = self._resolve()
        if prediction:
            return prediction["accuracy"]
        if source == "history_cell" and point:
            return point.get("accuracy") or 0
        return 0

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        _, source, prediction = self._resolve()
        attrs["location_source"] = source
        attrs["using_live_fix"] = source == "refresh"
        attrs["using_cell_location"] = source == "history_cell"
        attrs["predicted"] = prediction is not None
        if prediction:
            attrs["zones_used"] = prediction["zones_used"]
            attrs["zones_excluded"] = prediction["zones_excluded"]
            attrs["zones_ambiguous"] = prediction["ambiguous"]
        return attrs
