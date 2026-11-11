"""Fetches the month of prayer times and keeps a persistent copy."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EzanVaktiApi, EzanVaktiApiError
from .const import CONF_DISTRICT_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

Days = dict[str, dict[str, str]]


class EzanVaktiCoordinator(DataUpdateCoordinator[Days]):
    """Refreshes every 6 h. The API returns ~4 weeks ahead, so the stored copy keeps
    prayer times working through long outages and offline restarts."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(hours=6),
        )
        self.api = EzanVaktiApi(async_get_clientsession(hass))
        self._store: Store[Days] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._cache: Days = {}
        self.last_fetch_ok: bool | None = None

    async def _async_setup(self) -> None:
        self._cache = await self._store.async_load() or {}

    async def _async_update_data(self) -> Days:
        try:
            days = await self.api.times(self.config_entry.data[CONF_DISTRICT_ID])
        except EzanVaktiApiError as err:
            self.last_fetch_ok = False
            if self._cache:
                _LOGGER.warning("Prayer times refresh failed (%s); using the stored copy", err)
                return self._cache
            raise UpdateFailed(str(err)) from err
        self.last_fetch_ok = True
        # Keep yesterday onward from the old copy too, in case the new month is shorter.
        merged = {**self._cache, **days}
        today = min(days)
        merged = {k: v for k, v in merged.items() if k >= today}
        self._cache = merged
        await self._store.async_save(merged)
        return merged
