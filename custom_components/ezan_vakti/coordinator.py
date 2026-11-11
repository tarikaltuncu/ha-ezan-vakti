"""Keeps a stored copy of the prayer-time table and refreshes it only when it runs low."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EzanVaktiApi, EzanVaktiApiError
from .const import CONF_DISTRICT_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

Days = dict[str, dict[str, str]]

# One API call returns ~4 weeks. Call again only when fewer than this many days are left,
# i.e. about once every 3 weeks per location. Be gentle: it is a free community server.
MIN_DAYS_AHEAD = 7
# How often the stored copy is checked (locally). While a refresh is due but failing,
# this is also the retry interval, so an outage costs at most 4 calls a day.
CHECK_INTERVAL = timedelta(hours=6)


class EzanVaktiCoordinator(DataUpdateCoordinator[Days]):
    """Serves the stored table; the API is called only when it covers < 7 days ahead.

    Restarts, reloads and options changes never call the API while the copy is fresh.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=CHECK_INTERVAL,
        )
        self.api = EzanVaktiApi(async_get_clientsession(hass))
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._cache: Days = {}
        self.last_fetch: str | None = None
        self.last_fetch_ok: bool | None = None

    async def _async_setup(self) -> None:
        stored = await self._store.async_load() or {}
        if "days" in stored:
            self._cache = stored["days"] or {}
            self.last_fetch = stored.get("fetched_at")
        else:  # 0.1.0 stored the bare table
            self._cache = stored

    def _refresh_due(self) -> bool:
        target = (dt_util.now().date() + timedelta(days=MIN_DAYS_AHEAD)).isoformat()
        return target not in self._cache

    async def _async_update_data(self) -> Days:
        today = dt_util.now().date().isoformat()
        if not self._refresh_due():
            return {k: v for k, v in self._cache.items() if k >= today}
        try:
            days = await self.api.times(self.config_entry.data[CONF_DISTRICT_ID])
        except EzanVaktiApiError as err:
            self.last_fetch_ok = False
            if today in self._cache:
                _LOGGER.warning(
                    "Prayer times refresh failed (%s); using the stored copy, retrying in %s",
                    err, CHECK_INTERVAL,
                )
                return {k: v for k, v in self._cache.items() if k >= today}
            raise UpdateFailed(str(err)) from err
        self.last_fetch_ok = True
        self.last_fetch = dt_util.now().isoformat()
        # Keep any stored days the new table lacks (e.g. a shorter month), from today on.
        self._cache = {k: v for k, v in {**self._cache, **days}.items() if k >= today}
        await self._store.async_save({"fetched_at": self.last_fetch, "days": self._cache})
        _LOGGER.debug("Fetched prayer times up to %s", max(self._cache))
        return self._cache
