"""Scheduling and playback for one configured location."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_STOP,
    SERVICE_VOLUME_SET,
    STATE_HOME,
    STATE_ON,
    STATE_PLAYING,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_time, async_track_time_change
from homeassistant.util import dt as dt_util

from .audio import AudioManager
from .const import (
    CONF_ANNOUNCE,
    CONF_ENABLED,
    CONF_FAJR_OFFSET,
    CONF_FASTING,
    CONF_PRAYERS,
    CONF_PRESENCE_ENTITY,
    CONF_RAMADAN_AUTO,
    CONF_RESTORE_VOLUME,
    CONF_SPEAKERS,
    CONF_STYLE,
    CONF_VOLUME,
    DEFAULT_OPTIONS,
    PRAYERS,
    SIGNAL_UPDATE,
)
from .coordinator import EzanVaktiCoordinator
from .schedule import ezan_times, is_fasting, next_ezan, next_rollover, shown_times, vakit_times

_LOGGER = logging.getLogger(__name__)


class EzanVaktiRuntime:
    """Owns the next-ezan timer and plays the ezan on the configured speakers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: EzanVaktiCoordinator,
        audio: AudioManager,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.audio = audio
        self.next: tuple[str, datetime] | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None
        self._unsub_roll: CALLBACK_TYPE | None = None
        self._unsubs: list[CALLBACK_TYPE] = []
        self._restore_tasks: set[asyncio.Task] = set()

    # ── options ──────────────────────────────────────────────────────────────
    @property
    def options(self) -> dict[str, Any]:
        return {**DEFAULT_OPTIONS, **self.entry.options}

    @callback
    def set_option(self, key: str, value: Any) -> None:
        """Used by the switch/number/select entities; the options screen shows the same values."""
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, key: value}
        )

    # ── today's data ─────────────────────────────────────────────────────────
    @property
    def tz(self):
        return dt_util.get_default_time_zone()

    def row(self, offset: int = 0) -> dict[str, str] | None:
        day = dt_util.now().date() + timedelta(days=offset)
        return (self.coordinator.data or {}).get(day.isoformat())

    def today_row(self) -> dict[str, str] | None:
        return self.row(0)

    def day_vakits(self, offset: int = 0) -> dict[str, datetime]:
        row = self.row(offset)
        day = dt_util.now().date() + timedelta(days=offset)
        return vakit_times(day, row, self.tz) if row else {}

    def day_ezans(self, offset: int = 0) -> dict[str, datetime]:
        row = self.row(offset)
        if not row:
            return {}
        o = self.options
        return ezan_times(
            dt_util.now().date() + timedelta(days=offset), row, self.tz,
            fajr_offset=int(o[CONF_FAJR_OFFSET]), fasting=o[CONF_FASTING], ramadan_auto=o[CONF_RAMADAN_AUTO],
        )

    def shown_vakits(self) -> dict[str, datetime]:
        """What the vakit sensors show: today's, or tomorrow's once 5 min past."""
        return shown_times(dt_util.now(), self.day_vakits(0), self.day_vakits(1))

    def shown_fajr(self) -> datetime | None:
        today, tomorrow = self.day_ezans(0), self.day_ezans(1)
        return shown_times(
            dt_util.now(),
            {"fajr": today["fajr"]} if today else {},
            {"fajr": tomorrow["fajr"]} if tomorrow else {},
        ).get("fajr")

    def fasting_on(self, offset: int = 0) -> bool:
        row = self.row(offset) or {}
        return is_fasting(row, self.options[CONF_FASTING], self.options[CONF_RAMADAN_AUTO])

    def fasting_today(self) -> bool:
        return self.fasting_on(0)

    # ── lifecycle ────────────────────────────────────────────────────────────
    @callback
    def start(self) -> None:
        self._unsubs.append(self.coordinator.async_add_listener(self.reschedule))
        # Day rollover: today's sensors change even if nothing else does.
        self._unsubs.append(
            async_track_time_change(self.hass, lambda _now: self.reschedule(), hour=0, minute=0, second=5)
        )
        self.reschedule()

    @callback
    def stop(self) -> None:
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_roll:
            self._unsub_roll()
            self._unsub_roll = None
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for task in self._restore_tasks:
            task.cancel()

    @callback
    def reschedule(self) -> None:
        """(Re)arm the timer for the next enabled ezan and refresh all entities."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        o = self.options
        self.next = next_ezan(
            dt_util.now(), self.coordinator.data or {}, self.tz,
            fajr_offset=int(o[CONF_FAJR_OFFSET]), fasting=o[CONF_FASTING],
            ramadan_auto=o[CONF_RAMADAN_AUTO], prayers=o[CONF_PRAYERS] or [],
        )
        if self.next:
            self._unsub_timer = async_track_point_in_time(self.hass, self._fire, self.next[1])
        self._arm_rollover()
        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(self.entry.entry_id))

    @callback
    def _arm_rollover(self) -> None:
        """Refresh the entities when a passed vakit switches to tomorrow's time."""
        if self._unsub_roll:
            self._unsub_roll()
            self._unsub_roll = None
        today = {**self.day_vakits(0), **{f"ezan_{k}": v for k, v in self.day_ezans(0).items()}}
        at = next_rollover(dt_util.now(), today)
        if at:
            self._unsub_roll = async_track_point_in_time(self.hass, self._rolled, at)

    @callback
    def _rolled(self, _now: datetime) -> None:
        self._unsub_roll = None
        self.hass.loop.call_later(1, self._after_roll)

    @callback
    def _after_roll(self) -> None:
        self._arm_rollover()
        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(self.entry.entry_id))

    @callback
    def _fire(self, _now: datetime) -> None:
        self._unsub_timer = None
        prayer = self.next[0] if self.next else None
        # Move on to the next one first (a second later, so "now" is past this ezan).
        self.hass.loop.call_later(1, self.reschedule)
        if not prayer:
            return
        o = self.options
        if not o[CONF_ENABLED]:
            _LOGGER.debug("Ezan %s skipped: disabled", prayer)
            return
        if not self.presence_ok():
            _LOGGER.debug("Ezan %s skipped: presence entity says nobody is home", prayer)
            return
        self.entry.async_create_background_task(self.hass, self.play(prayer), f"ezan_vakti play {prayer}")

    def presence_ok(self) -> bool:
        entity_id = (self.options.get(CONF_PRESENCE_ENTITY) or "").strip()
        if not entity_id:
            return True
        state = self.hass.states.get(entity_id)
        if state is None:
            return True  # misconfigured → don't silently swallow every ezan
        if entity_id.startswith("zone."):
            try:
                return int(state.state) > 0
            except ValueError:
                return True
        return state.state in (STATE_ON, STATE_HOME)

    # ── playback ─────────────────────────────────────────────────────────────
    async def play(
        self, prayer: str | None = None, style: str | None = None, speakers: list[str] | None = None
    ) -> None:
        o = self.options
        speakers = speakers or o[CONF_SPEAKERS]
        if not speakers:
            _LOGGER.warning("No speaker configured for Ezan Vakti; set one in the integration options")
            return
        usable = []
        for s in speakers:
            st = self.hass.states.get(s)
            features = st.attributes.get(ATTR_SUPPORTED_FEATURES, 0) if st else 0
            if st is None or features & MediaPlayerEntityFeature.PLAY_MEDIA:
                usable.append(s)  # unknown/unavailable ones are tried anyway
            else:
                _LOGGER.warning("%s cannot play media; skipping it for the ezan", s)
        speakers = usable
        if not speakers:
            return
        if prayer not in PRAYERS:
            prayer = self.next[0] if self.next else "dhuhr"
        url = await self.audio.url_for(self.hass, style or o[CONF_STYLE], prayer, o)
        if not url:
            _LOGGER.error("No ezan audio available for %s/%s", style or o[CONF_STYLE], prayer)
            return
        volume = max(0, min(100, int(o[CONF_VOLUME]))) / 100
        previous = {
            s: st.attributes.get(ATTR_MEDIA_VOLUME_LEVEL)
            for s in speakers
            if (st := self.hass.states.get(s)) is not None
        }
        try:
            await self.hass.services.async_call(
                MP_DOMAIN, SERVICE_VOLUME_SET,
                {ATTR_ENTITY_ID: speakers, ATTR_MEDIA_VOLUME_LEVEL: volume}, blocking=True,
            )
        except Exception as err:  # noqa: BLE001 - some speakers are off / don't support it
            _LOGGER.debug("volume_set failed: %s", err)
        data: dict[str, Any] = {
            ATTR_ENTITY_ID: speakers,
            ATTR_MEDIA_CONTENT_ID: url,
            ATTR_MEDIA_CONTENT_TYPE: "music",
        }
        if o[CONF_ANNOUNCE]:
            data[ATTR_MEDIA_ANNOUNCE] = True
        _LOGGER.info("Playing ezan %s on %s: %s", prayer, speakers, url)
        try:
            await self.hass.services.async_call(MP_DOMAIN, SERVICE_PLAY_MEDIA, data, blocking=True)
        except Exception as err:  # noqa: BLE001 - log it; a scheduled ezan has no caller to tell
            _LOGGER.error("Could not play the ezan on %s: %s", speakers, err)
            return
        if o[CONF_RESTORE_VOLUME]:
            restore = {s: v for s, v in previous.items() if isinstance(v, (int, float)) and abs(v - volume) > 0.01}
            if restore:
                task = self.hass.async_create_background_task(
                    self._restore_after(restore), "ezan_vakti restore volume"
                )
                self._restore_tasks.add(task)
                task.add_done_callback(self._restore_tasks.discard)

    async def _restore_after(self, restore: dict[str, float]) -> None:
        """Wait (≤ 8 min) until the speakers stop playing, then put their volume back."""
        loop_end = dt_util.utcnow() + timedelta(minutes=8)
        started = dt_util.utcnow() + timedelta(seconds=30)
        seen_playing = False
        while dt_util.utcnow() < loop_end:
            await asyncio.sleep(2)
            playing = any(
                (st := self.hass.states.get(s)) is not None and st.state == STATE_PLAYING for s in restore
            )
            seen_playing = seen_playing or playing
            if (seen_playing and not playing) or (not seen_playing and dt_util.utcnow() > started):
                break
        for speaker, level in restore.items():
            try:
                await self.hass.services.async_call(
                    MP_DOMAIN, SERVICE_VOLUME_SET,
                    {ATTR_ENTITY_ID: speaker, ATTR_MEDIA_VOLUME_LEVEL: level}, blocking=True,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("restoring volume of %s failed: %s", speaker, err)

    async def stop_playback(self, speakers: list[str] | None = None) -> None:
        speakers = speakers or self.options[CONF_SPEAKERS]
        if speakers:
            await self.hass.services.async_call(
                MP_DOMAIN, SERVICE_MEDIA_STOP, {ATTR_ENTITY_ID: speakers}, blocking=True
            )
