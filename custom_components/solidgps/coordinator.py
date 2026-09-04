"""Data update coordinator for SolidGPS."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SolidGPS
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SolidGPSCoordinator(DataUpdateCoordinator):
    """Fetch data from SolidGPS on a schedule."""

    def __init__(self, hass: HomeAssistant, api: SolidGPS) -> None:
        self.api = api
        self._cursor: dict[str, str] = {}
        self._live_fix: dict[str, dict] = {}
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict:
        try:
            # Refresh dashboard to get updated csrf_token / device list
            await self.hass.async_add_executor_job(self.api.refresh)

            data = {}
            for imei in self.api.devices:
                tracking = await self.hass.async_add_executor_job(
                    self.api.get_tracking_data, imei
                )
                # New API: response is {success, status, data: {devices: {imei: {...}}}}
                device_data = {}
                if isinstance(tracking, dict) and tracking.get("success"):
                    device_data = tracking.get("data", {}).get("devices", {}).get(imei, {})
                # Merge static dashboard info (nickname, color, etc.) with live tracking data
                merged = {**self.api.devices[imei], **device_data}

                # Poll the lightweight refresh endpoint for the freshest GPS fix.
                # It only returns a device entry when something new was reported,
                # so keep the last known fix/cursor around between update cycles.
                refresh_resp = await self.hass.async_add_executor_job(
                    self.api.get_refresh_data, imei, self._cursor.get(imei)
                )
                if isinstance(refresh_resp, dict) and refresh_resp.get("success"):
                    r_data = refresh_resp.get("data", {})
                    if r_data.get("update_time"):
                        self._cursor[imei] = r_data["update_time"]
                    r_devices = r_data.get("devices", {})
                    r_device = r_devices.get(imei) if isinstance(r_devices, dict) else None
                    if r_device and r_device.get("gps_data"):
                        self._live_fix[imei] = max(
                            r_device["gps_data"], key=lambda p: p.get("utc", 0)
                        )

                if imei in self._live_fix:
                    merged["live_fix"] = self._live_fix[imei]

                data[imei] = {
                    "device_info": merged,
                    "tracking": tracking,
                }
            return data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with SolidGPS: {err}") from err
