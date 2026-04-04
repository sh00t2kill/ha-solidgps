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
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict:
        try:
            # Refresh dashboard to get latest device_info (battery, status, etc.)
            await self.hass.async_add_executor_job(self.api.refresh)

            data = {}
            for imei in self.api.devices:
                tracking = await self.hass.async_add_executor_job(
                    self.api.get_tracking_data, imei
                )
                data[imei] = {
                    "device_info": self.api.devices[imei],
                    "tracking": tracking,
                }
            return data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with SolidGPS: {err}") from err
