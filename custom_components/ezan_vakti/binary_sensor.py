"""On when today's Sabah ezanı is at İmsak (fasting switch, or Ramadan with auto on)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EzanVaktiConfigEntry
from .entity import EzanVaktiEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: EzanVaktiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([FastingActive(entry.runtime_data)])


class FastingActive(EzanVaktiEntity, BinarySensorEntity):
    def __init__(self, runtime) -> None:
        super().__init__(runtime, "fasting_active")

    @property
    def is_on(self) -> bool:
        return self.runtime.fasting_today()
