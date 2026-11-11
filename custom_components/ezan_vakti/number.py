"""Sabah ezanı offset before sunrise, and the ezan volume — mirrored in the options."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EzanVaktiConfigEntry
from .const import CONF_FAJR_OFFSET, CONF_VOLUME
from .entity import EzanVaktiEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: EzanVaktiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    rt = entry.runtime_data
    async_add_entities(
        [
            OptionNumber(rt, CONF_FAJR_OFFSET, 0, 90, 1, UnitOfTime.MINUTES, NumberMode.BOX),
            OptionNumber(rt, CONF_VOLUME, 0, 100, 5, PERCENTAGE, NumberMode.SLIDER),
        ]
    )


class OptionNumber(EzanVaktiEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime, option, lo, hi, step, unit, mode) -> None:
        super().__init__(runtime, option)
        self._option = option
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_mode = mode

    @property
    def native_value(self) -> float:
        return float(self.runtime.options[self._option])

    async def async_set_native_value(self, value: float) -> None:
        self.runtime.set_option(self._option, int(value))
