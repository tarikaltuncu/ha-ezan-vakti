"""Vakits and the Sabah ezanı time (today's, or tomorrow's once 5 min past), the next ezan and the countdown."""

from __future__ import annotations

from datetime import datetime
import math

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import EzanVaktiConfigEntry
from .const import PRAYERS, VAKITS
from .entity import EzanVaktiEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: EzanVaktiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    rt = entry.runtime_data
    async_add_entities(
        [
            *(VakitSensor(rt, v) for v in VAKITS),
            FajrEzanSensor(rt),
            NextEzanSensor(rt),
            NextEzanTimeSensor(rt),
            CountdownSensor(rt),
            HijriSensor(rt),
        ]
    )


class VakitSensor(EzanVaktiEntity, SensorEntity):
    """One Diyanet vakit: today's time until 5 min after it, then tomorrow's."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, runtime, vakit: str) -> None:
        super().__init__(runtime, vakit)
        self._vakit = vakit

    @property
    def native_value(self) -> datetime | None:
        return self.runtime.shown_vakits().get(self._vakit)


class FajrEzanSensor(EzanVaktiEntity, SensorEntity):
    """When the Sabah ezanı plays (Güneş − offset, or İmsak when fasting); tomorrow's once 5 min past."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, runtime) -> None:
        super().__init__(runtime, "fajr_ezan")

    @property
    def native_value(self) -> datetime | None:
        return self.runtime.shown_fajr()

    @property
    def extra_state_attributes(self) -> dict:
        shown = self.native_value
        offset = 1 if shown and shown.date() > dt_util.now().date() else 0
        return {"fasting": self.runtime.fasting_on(offset)}


class NextEzanSensor(EzanVaktiEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(PRAYERS)

    def __init__(self, runtime) -> None:
        super().__init__(runtime, "next_ezan")

    @property
    def native_value(self) -> str | None:
        return self.runtime.next[0] if self.runtime.next else None

    @property
    def extra_state_attributes(self) -> dict:
        nxt = self.runtime.next
        return {"time": dt_util.as_local(nxt[1]).strftime("%H:%M") if nxt else None}


class NextEzanTimeSensor(EzanVaktiEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, runtime) -> None:
        super().__init__(runtime, "next_ezan_time")

    @property
    def native_value(self) -> datetime | None:
        return self.runtime.next[1] if self.runtime.next else None


class CountdownSensor(EzanVaktiEntity, SensorEntity):
    """Minutes left until the next ezan, updated every minute."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0

    def __init__(self, runtime) -> None:
        super().__init__(runtime, "next_ezan_countdown")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_change(self.hass, self._tick, second=0))

    @callback
    def _tick(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        nxt = self.runtime.next
        if not nxt:
            return None
        return max(0, math.ceil((nxt[1] - dt_util.now()).total_seconds() / 60))

    @property
    def extra_state_attributes(self) -> dict:
        nxt = self.runtime.next
        if not nxt:
            return {}
        mins = self.native_value or 0
        return {
            "prayer": nxt[0],
            "time": dt_util.as_local(nxt[1]).strftime("%H:%M"),
            "hh_mm": f"{mins // 60}:{mins % 60:02d}",
        }


class HijriSensor(EzanVaktiEntity, SensorEntity):
    def __init__(self, runtime) -> None:
        super().__init__(runtime, "hijri_date")

    @property
    def native_value(self) -> str | None:
        row = self.runtime.today_row()
        return row.get("hijri") or None if row else None
