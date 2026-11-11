"""Base entity: one device per configured location, refreshed on schedule changes."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import API_BASE, DOMAIN, SIGNAL_UPDATE
from .runtime import EzanVaktiRuntime


class EzanVaktiEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: EzanVaktiRuntime, key: str) -> None:
        self.runtime = runtime
        entry = runtime.entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Ezan Vakti {entry.title}",
            manufacturer="Diyanet (via ezanvakti.emushaf.net)",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=API_BASE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE.format(self.runtime.entry.entry_id), self.async_write_ha_state
            )
        )
