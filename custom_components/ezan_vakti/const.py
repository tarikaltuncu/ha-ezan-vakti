"""Constants for the Ezan Vakti integration."""

from __future__ import annotations

DOMAIN = "ezan_vakti"
API_BASE = "https://ezanvakti.emushaf.net"

# Config entry data (location; fixed per entry)
CONF_COUNTRY_ID = "country_id"
CONF_CITY_ID = "city_id"
CONF_DISTRICT_ID = "district_id"
CONF_LOCATION_NAME = "location_name"

# Options (the settings screen; also changed live by the switch/number/select entities)
CONF_ENABLED = "enabled"
CONF_SPEAKERS = "speakers"
CONF_VOLUME = "volume"
CONF_STYLE = "style"
CONF_PRAYERS = "prayers"
CONF_FAJR_OFFSET = "fajr_minutes_before_sunrise"
CONF_FASTING = "fasting"
CONF_RAMADAN_AUTO = "ramadan_auto"
CONF_PRESENCE_ENTITY = "presence_entity"
CONF_RESTORE_VOLUME = "restore_volume"
CONF_ANNOUNCE = "announce"
CONF_CUSTOM_FAJR_URL = "custom_fajr_url"
CONF_CUSTOM_ADHAN_URL = "custom_adhan_url"

# Vakits as returned by the API (Diyanet), in day order.
VAKITS = ("imsak", "sunrise", "dhuhr", "asr", "maghrib", "isha")
API_VAKIT_KEYS = {
    "imsak": "Imsak",
    "sunrise": "Gunes",
    "dhuhr": "Ogle",
    "asr": "Ikindi",
    "maghrib": "Aksam",
    "isha": "Yatsi",
}

# The five ezans. There is no ezan at İmsak or Güneş (sunrise).
PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")

STYLE_RANDOM = "random"
STYLE_CUSTOM = "custom"

DEFAULT_OPTIONS = {
    CONF_ENABLED: True,
    CONF_SPEAKERS: [],
    CONF_VOLUME: 30,
    CONF_STYLE: "turkish_sehitoglu",
    CONF_PRAYERS: list(PRAYERS),
    CONF_FAJR_OFFSET: 15,
    CONF_FASTING: False,
    CONF_RAMADAN_AUTO: True,
    CONF_PRESENCE_ENTITY: "",
    CONF_RESTORE_VOLUME: True,
    CONF_ANNOUNCE: False,
    CONF_CUSTOM_FAJR_URL: "",
    CONF_CUSTOM_ADHAN_URL: "",
}

AUDIO_DIR = "ezan_vakti"  # under the HA config dir
AUDIO_URL = "/ezan_vakti/audio"  # static path served by this integration

SIGNAL_UPDATE = f"{DOMAIN}_update_{{}}"  # .format(entry_id)

SERVICE_PLAY = "play"
SERVICE_STOP = "stop"
SERVICE_DOWNLOAD = "download_audio"
