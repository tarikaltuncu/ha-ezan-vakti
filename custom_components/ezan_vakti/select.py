"""Recording style — mirrored in the options."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EzanVaktiConfigEntry
from .audio import STYLE_OPTIONS
from .const import CONF_STYLE
from .entity import EzanVaktiEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: EzanVaktiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([StyleSelect(entry.runtime_data)])


class StyleSelect(EzanVaktiEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = STYLE_OPTIONS

    def __init__(self, runtime) -> None:
        super().__init__(runtime, "style")

    @property
    def current_option(self) -> str:
        return self.runtime.options[CONF_STYLE]

    async def async_select_option(self, option: str) -> None:
        self.runtime.set_option(CONF_STYLE, option)
