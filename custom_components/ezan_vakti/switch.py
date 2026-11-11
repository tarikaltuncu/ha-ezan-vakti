"""Ezan on/off, fasting (Sabah at İmsak), auto-fasting in Ramadan — mirrored in the options."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EzanVaktiConfigEntry
from .const import CONF_ENABLED, CONF_FASTING, CONF_RAMADAN_AUTO
from .entity import EzanVaktiEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: EzanVaktiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    rt = entry.runtime_data
    async_add_entities(
        [
            OptionSwitch(rt, CONF_ENABLED, None),
            OptionSwitch(rt, CONF_FASTING, None),
            OptionSwitch(rt, CONF_RAMADAN_AUTO, EntityCategory.CONFIG),
        ]
    )


class OptionSwitch(EzanVaktiEntity, SwitchEntity):
    def __init__(self, runtime, option: str, category: EntityCategory | None) -> None:
        super().__init__(runtime, option)
        self._option = option
        self._attr_entity_category = category

    @property
    def is_on(self) -> bool:
        return bool(self.runtime.options[self._option])

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.runtime.set_option(self._option, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.runtime.set_option(self._option, False)
