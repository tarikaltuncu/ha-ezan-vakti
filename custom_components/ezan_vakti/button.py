"""Play the next ezan now (test) / stop playback."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EzanVaktiConfigEntry
from .entity import EzanVaktiEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: EzanVaktiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    rt = entry.runtime_data
    async_add_entities([PlayButton(rt), StopButton(rt)])


class PlayButton(EzanVaktiEntity, ButtonEntity):
    def __init__(self, runtime) -> None:
        super().__init__(runtime, "play_next")

    async def async_press(self) -> None:
        await self.runtime.play()


class StopButton(EzanVaktiEntity, ButtonEntity):
    def __init__(self, runtime) -> None:
        super().__init__(runtime, "stop")

    async def async_press(self) -> None:
        await self.runtime.stop_playback()
