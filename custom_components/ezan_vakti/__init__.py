"""Ezan Vakti: Diyanet prayer times for any location, with the ezan on your speakers."""

from __future__ import annotations

from pathlib import Path

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .audio import CATALOG, STYLE_OPTIONS, AudioManager
from .const import (
    AUDIO_DIR,
    AUDIO_URL,
    CONF_STYLE,
    DOMAIN,
    PRAYERS,
    SERVICE_DOWNLOAD,
    SERVICE_PLAY,
    SERVICE_STOP,
)
from .coordinator import EzanVaktiCoordinator
from .runtime import EzanVaktiRuntime

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type EzanVaktiConfigEntry = ConfigEntry[EzanVaktiRuntime]

ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_PRAYER = "prayer"
ATTR_STYLE = "style"
ATTR_SPEAKERS = "speakers"

PLAY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY): cv.string,
        vol.Optional(ATTR_PRAYER): vol.In(PRAYERS),
        vol.Optional(ATTR_STYLE): vol.In(STYLE_OPTIONS),
        vol.Optional(ATTR_SPEAKERS): cv.entity_ids,
    }
)
STOP_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY): cv.string, vol.Optional(ATTR_SPEAKERS): cv.entity_ids}
)
DOWNLOAD_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_STYLE): vol.Any("all", vol.In(list(CATALOG)))}
)


def _audio(hass: HomeAssistant) -> AudioManager:
    return hass.data[DOMAIN]["audio"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Shared audio store, static path and actions (once, for all entries)."""
    base = Path(hass.config.path(AUDIO_DIR))
    await hass.async_add_executor_job(lambda: base.mkdir(parents=True, exist_ok=True))
    hass.data[DOMAIN] = {"audio": AudioManager(base, async_get_clientsession(hass))}
    await hass.http.async_register_static_paths(
        [StaticPathConfig(AUDIO_URL, str(base), cache_headers=False)]
    )

    def _runtime(call: ServiceCall) -> EzanVaktiRuntime:
        entries = [
            e for e in hass.config_entries.async_loaded_entries(DOMAIN)
            if ATTR_CONFIG_ENTRY not in call.data or e.entry_id == call.data[ATTR_CONFIG_ENTRY]
        ]
        if not entries:
            raise ServiceValidationError("No loaded Ezan Vakti entry matches")
        return entries[0].runtime_data

    async def _play(call: ServiceCall) -> None:
        await _runtime(call).play(
            call.data.get(ATTR_PRAYER), call.data.get(ATTR_STYLE), call.data.get(ATTR_SPEAKERS)
        )

    async def _stop(call: ServiceCall) -> None:
        await _runtime(call).stop_playback(call.data.get(ATTR_SPEAKERS))

    async def _download(call: ServiceCall) -> None:
        style = call.data.get(ATTR_STYLE, "all")
        for s in (list(CATALOG) if style == "all" else [style]):
            await _audio(hass).ensure(hass, s)

    hass.services.async_register(DOMAIN, SERVICE_PLAY, _play, schema=PLAY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_STOP, _stop, schema=STOP_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DOWNLOAD, _download, schema=DOWNLOAD_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EzanVaktiConfigEntry) -> bool:
    coordinator = EzanVaktiCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    runtime = EzanVaktiRuntime(hass, entry, coordinator, _audio(hass))
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    runtime.start()
    entry.async_on_unload(runtime.stop)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    _prefetch(hass, entry)
    return True


@callback
def _prefetch(hass: HomeAssistant, entry: EzanVaktiConfigEntry) -> None:
    """Download the chosen style in the background so the first ezan isn't late."""
    style = entry.runtime_data.options[CONF_STYLE]
    if style in CATALOG:
        entry.async_create_background_task(
            hass, _audio(hass).ensure(hass, style), f"ezan_vakti download {style}"
        )


async def _options_updated(hass: HomeAssistant, entry: EzanVaktiConfigEntry) -> None:
    """Settings changed (options screen or a switch/number/select): no reload needed."""
    entry.runtime_data.reschedule()
    _prefetch(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: EzanVaktiConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
