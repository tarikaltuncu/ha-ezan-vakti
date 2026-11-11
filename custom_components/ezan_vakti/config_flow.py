"""Setup (location → speakers) and the settings screen (options flow)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import EzanVaktiApi, EzanVaktiApiError
from .audio import STYLE_OPTIONS
from .const import (
    CONF_ANNOUNCE,
    CONF_CITY_ID,
    CONF_COUNTRY_ID,
    CONF_CUSTOM_ADHAN_URL,
    CONF_CUSTOM_FAJR_URL,
    CONF_DISTRICT_ID,
    CONF_ENABLED,
    CONF_FAJR_OFFSET,
    CONF_FASTING,
    CONF_LOCATION_NAME,
    CONF_PRAYERS,
    CONF_PRESENCE_ENTITY,
    CONF_RAMADAN_AUTO,
    CONF_RESTORE_VOLUME,
    CONF_SPEAKERS,
    CONF_STYLE,
    CONF_VOLUME,
    DEFAULT_OPTIONS,
    DOMAIN,
    PRAYERS,
)

# A few ISO country codes → the API's country id, to preselect the user's country.
_COUNTRY_HINTS = {
    "TR": "2", "NL": "4", "AZ": "5", "BE": "11", "SE": "12", "DE": "13", "GB": "15",
    "FR": "21", "DK": "26", "US": "33", "AT": "35", "CH": "49", "CA": "52", "AU": "59",
    "CN": "61", "SA": "64", "PK": "77", "MY": "107", "ID": "117", "UZ": "131",
    "IN": "187", "EG": "189", "SY": "191", "PS": "204",
}


def _options(choices: dict[str, str]) -> list[SelectOptionDict]:
    return [
        SelectOptionDict(value=k, label=v)
        for k, v in sorted(choices.items(), key=lambda kv: kv[1].casefold())
    ]


def _settings_schema(o: dict[str, Any], *, full: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if full:
        fields[vol.Required(CONF_ENABLED, default=o[CONF_ENABLED])] = BooleanSelector()
    fields[vol.Optional(CONF_SPEAKERS, default=o[CONF_SPEAKERS])] = EntitySelector(
        EntitySelectorConfig(
            domain="media_player",
            multiple=True,
            supported_features=["media_player.MediaPlayerEntityFeature.PLAY_MEDIA"],
        )
    )
    fields[vol.Required(CONF_STYLE, default=o[CONF_STYLE])] = SelectSelector(
        SelectSelectorConfig(options=STYLE_OPTIONS, translation_key="style", mode=SelectSelectorMode.DROPDOWN)
    )
    fields[vol.Required(CONF_VOLUME, default=o[CONF_VOLUME])] = NumberSelector(
        NumberSelectorConfig(min=0, max=100, step=5, unit_of_measurement="%", mode=NumberSelectorMode.SLIDER)
    )
    fields[vol.Required(CONF_PRAYERS, default=o[CONF_PRAYERS])] = SelectSelector(
        SelectSelectorConfig(options=list(PRAYERS), multiple=True, translation_key="prayer",
                             mode=SelectSelectorMode.LIST)
    )
    fields[vol.Required(CONF_FAJR_OFFSET, default=o[CONF_FAJR_OFFSET])] = NumberSelector(
        NumberSelectorConfig(min=0, max=90, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX)
    )
    fields[vol.Required(CONF_FASTING, default=o[CONF_FASTING])] = BooleanSelector()
    fields[vol.Required(CONF_RAMADAN_AUTO, default=o[CONF_RAMADAN_AUTO])] = BooleanSelector()
    fields[
        vol.Optional(CONF_PRESENCE_ENTITY, description={"suggested_value": o[CONF_PRESENCE_ENTITY] or None})
    ] = EntitySelector(
        EntitySelectorConfig(
            domain=["binary_sensor", "input_boolean", "person", "device_tracker", "group", "zone"]
        )
    )
    if full:
        fields[vol.Required(CONF_RESTORE_VOLUME, default=o[CONF_RESTORE_VOLUME])] = BooleanSelector()
        fields[vol.Required(CONF_ANNOUNCE, default=o[CONF_ANNOUNCE])] = BooleanSelector()
        fields[
            vol.Optional(CONF_CUSTOM_FAJR_URL, description={"suggested_value": o[CONF_CUSTOM_FAJR_URL] or None})
        ] = TextSelector()
        fields[
            vol.Optional(CONF_CUSTOM_ADHAN_URL, description={"suggested_value": o[CONF_CUSTOM_ADHAN_URL] or None})
        ] = TextSelector()
    return vol.Schema(fields)


def _clean(user_input: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    out = {**base, **user_input}
    for key in (CONF_PRESENCE_ENTITY, CONF_CUSTOM_FAJR_URL, CONF_CUSTOM_ADHAN_URL):
        out[key] = (user_input.get(key) or "").strip()
    out[CONF_VOLUME] = int(out[CONF_VOLUME])
    out[CONF_FAJR_OFFSET] = int(out[CONF_FAJR_OFFSET])
    return out


class EzanVaktiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Country → city → district → speakers."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._names: dict[str, str] = {}
        self._choices: dict[str, str] = {}

    @property
    def _api(self) -> EzanVaktiApi:
        return EzanVaktiApi(async_get_clientsession(self.hass))

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data[CONF_COUNTRY_ID] = user_input[CONF_COUNTRY_ID]
            self._names["country"] = self._choices.get(user_input[CONF_COUNTRY_ID], "")
            return await self.async_step_city()
        try:
            self._choices = await self._api.countries()
        except EzanVaktiApiError:
            return self.async_abort(reason="cannot_connect")
        hint = _COUNTRY_HINTS.get(self.hass.config.country or "")
        key = vol.Required(CONF_COUNTRY_ID, default=hint) if hint in self._choices else vol.Required(CONF_COUNTRY_ID)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({key: SelectSelector(SelectSelectorConfig(options=_options(self._choices)))}),
        )

    async def async_step_city(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data[CONF_CITY_ID] = user_input[CONF_CITY_ID]
            self._names["city"] = self._choices.get(user_input[CONF_CITY_ID], "")
            return await self.async_step_district()
        try:
            self._choices = await self._api.cities(self._data[CONF_COUNTRY_ID])
        except EzanVaktiApiError:
            return self.async_abort(reason="cannot_connect")
        return self.async_show_form(
            step_id="city",
            data_schema=vol.Schema(
                {vol.Required(CONF_CITY_ID): SelectSelector(SelectSelectorConfig(options=_options(self._choices)))}
            ),
            description_placeholders={"country": self._names.get("country", "")},
        )

    async def async_step_district(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            district = user_input[CONF_DISTRICT_ID]
            await self.async_set_unique_id(district)
            self._abort_if_unique_id_configured()
            name = self._choices.get(district, district)
            city = self._names.get("city", "")
            self._data[CONF_DISTRICT_ID] = district
            self._data[CONF_LOCATION_NAME] = name.title() if name == city or not city else f"{name.title()}, {city.title()}"
            return await self.async_step_settings()
        try:
            self._choices = await self._api.districts(self._data[CONF_CITY_ID])
        except EzanVaktiApiError:
            return self.async_abort(reason="cannot_connect")
        return self.async_show_form(
            step_id="district",
            data_schema=vol.Schema(
                {vol.Required(CONF_DISTRICT_ID): SelectSelector(SelectSelectorConfig(options=_options(self._choices)))}
            ),
            description_placeholders={"city": self._names.get("city", "")},
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=self._data[CONF_LOCATION_NAME],
                data=self._data,
                options=_clean(user_input, DEFAULT_OPTIONS),
            )
        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(DEFAULT_OPTIONS, full=False),
            description_placeholders={"location": self._data[CONF_LOCATION_NAME]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EzanVaktiOptionsFlow()


class EzanVaktiOptionsFlow(OptionsFlow):
    """The settings screen: Settings → Devices & services → Ezan Vakti → Configure."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = {**DEFAULT_OPTIONS, **self.config_entry.options}
        if user_input is not None:
            return self.async_create_entry(data=_clean(user_input, current))
        return self.async_show_form(step_id="init", data_schema=_settings_schema(current, full=True))
