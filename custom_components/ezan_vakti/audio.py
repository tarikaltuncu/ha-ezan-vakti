"""Ezan recordings: a catalog of public archive.org links, downloaded on demand.

Nothing is redistributed by this repository: each Home Assistant downloads the files it
needs into `<config>/ezan_vakti/<style>/` the first time a style is used (or via the
`ezan_vakti.download_audio` action). If ffmpeg is available the files are loudness-
normalised (EBU R128, -16 LUFS) so one volume level sounds the same for every style.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import aiohttp

from .const import (
    AUDIO_URL,
    CONF_CUSTOM_ADHAN_URL,
    CONF_CUSTOM_FAJR_URL,
    PRAYERS,
    STYLE_CUSTOM,
    STYLE_RANDOM,
)

_LOGGER = logging.getLogger(__name__)


def _ia(item: str, name: str) -> str:
    return f"https://archive.org/download/{item}/{quote(name)}"


@dataclass(frozen=True)
class Style:
    """A recording set. Either one file per prayer (`per_prayer`), or `fajr` + `adhan`."""

    name: str
    files: dict[str, str]  # key → source URL; keys are PRAYERS or "fajr"/"adhan"
    notes: str = ""
    per_prayer: bool = field(default=False)

    def key_for(self, prayer: str) -> str | None:
        if self.per_prayer:
            return prayer if prayer in self.files else None
        if prayer == "fajr":
            return "fajr" if "fajr" in self.files else None
        return "adhan"


# Turkish sets follow the two most common makam-per-vakit schemes. There is no single
# binding rule; see README.
CATALOG: dict[str, Style] = {
    "turkish_sehitoglu": Style(
        name="Turkish – Abdulkadir Şehitoğlu (Saba · Rast · Hicaz · Segâh · Uşşak)",
        per_prayer=True,
        files={
            "fajr": _ia("ezanlardinle", "Sabah Ezanı_Sabah_ Abdulkadir Şehitoğlu TheislamForum.com (128kbit).m4a"),
            "dhuhr": _ia("ezanlardinle", "Öğle Ezanı_Rast_ Abdulkadir Şehitoğlu TheislamForum.com (128kbit).m4a"),
            "asr": _ia("ezanlardinle", "İkindi Ezanı_Hicaz_ Abdulkadir Şehitoğlu TheislamForum.com (128kbit).m4a"),
            "maghrib": _ia("ezanlardinle", "Akşam Ezanı_Segah_ Abdulkadir Şehitoğlu TheislamForum.com (128kbit).m4a"),
            "isha": _ia("ezanlardinle", "Yatsı Ezanı_Uşşak_ Abdulkadir Şehitoğlu TheislamForum.com (128kbit).m4a"),
        },
    ),
    "turkish_erarabaci": Style(
        name="Turkish – Mehmet Erarabacı (Saba · Uşşak · Rast · Segâh · Hicaz)",
        per_prayer=True,
        notes="Sabah ezanı by İlhan Tok (Saba).",
        files={
            "fajr": _ia("ezanlardinle", "İlhan Tok-Sabah Ezanı (Saba Makamı) (128kbit).m4a"),
            "dhuhr": _ia("ezanlardinle", "Mehmet Erarabacı - Uşşak Ezan (192kbit).m4a"),
            "asr": _ia("ezanlardinle", "Mehmet Erarabacı - Rast Ezan (192kbit).m4a"),
            "maghrib": _ia("ezanlardinle", "Mehmet Erarabacı - Segah Ezan (192kbit).m4a"),
            "isha": _ia("ezanlardinle", "Mehmet Erarabacı - Hicaz Ezanı (192kbit).m4a"),
        },
    ),
    "makkah": Style(
        name="Makkah – Masjid al-Haram",
        files={
            "fajr": _ia("adhan_202303", "alfajr-alharam-almakiya.mp3"),
            "adhan": _ia("ismail-cosar-hicaz", "Mekka - ali almula.mp3"),
        },
    ),
    "madinah": Style(
        name="Madinah – Masjid an-Nabawi",
        files={
            "fajr": _ia("ezanlardinle", "Medinede Sabah Ezanı (256kbit).m4a"),
            "adhan": _ia("ezanlardinle", "Live Ezani ne Medine. (256kbit).m4a"),
        },
    ),
    "mishary": Style(
        name="Kuwait – Mishary Rashid Alafasy",
        files={
            "fajr": _ia("ismail-cosar-hicaz", "Mishari Alafasy - Al-Fajer.mp3"),
            "adhan": _ia("adhans_sunnah", "adhan_mishari.mp3"),
        },
    ),
    "egyptian": Style(
        name="Egyptian – Abdul Basit Abdus Samad",
        notes="Fajr recording is low bitrate.",
        files={
            "fajr": _ia("AdhaN_M_up-by-muslem", "036--.mp3"),
            "adhan": _ia("ismail-cosar-hicaz", "abdul baset abdul samad.mp3"),
        },
    ),
    "palestinian": Style(
        name="Palestinian – al-Aqsa / Dome of the Rock",
        notes="Fajr recording is low bitrate.",
        files={
            "fajr": _ia("AdhaN_M_up-by-muslem", "069--.mp3"),
            "adhan": _ia("ezanlardinle", "DOME OF THE ROCK JERUSALEM PALESTINE ATHAN AZAN (256kbit).m4a"),
        },
    ),
    "syrian": Style(
        name="Syrian",
        notes="Low bitrate; no Fajr recording (Makkah's Fajr is used).",
        files={"adhan": _ia("AdhaN_M_up-by-muslem", "065--.mp3")},
    ),
}

FALLBACK_FAJR_STYLE = "makkah"
STYLE_OPTIONS = [*CATALOG, STYLE_RANDOM, STYLE_CUSTOM]


class AudioManager:
    """Downloads, normalises and resolves ezan files."""

    def __init__(self, base_dir: Path, session: aiohttp.ClientSession) -> None:
        self.base_dir = base_dir
        self._session = session
        self._locks: dict[str, asyncio.Lock] = {}
        self._ffmpeg = shutil.which("ffmpeg")

    def _manifest_path(self, style: str) -> Path:
        return self.base_dir / style / "manifest.json"

    def _read_manifest(self, style: str) -> dict[str, str]:
        try:
            return json.loads(self._manifest_path(style).read_text())
        except (OSError, ValueError):
            return {}

    def downloaded(self, style: str) -> dict[str, str]:
        """key → filename for files present on disk (blocking; run in executor)."""
        manifest = self._read_manifest(style)
        return {k: f for k, f in manifest.items() if (self.base_dir / style / f).is_file()}

    async def ensure(self, hass, style: str) -> dict[str, str]:
        """Download any missing files of `style`. Returns key → filename."""
        if style not in CATALOG:
            return {}
        lock = self._locks.setdefault(style, asyncio.Lock())
        async with lock:
            have = await hass.async_add_executor_job(self.downloaded, style)
            missing = {k: u for k, u in CATALOG[style].files.items() if k not in have}
            if not missing:
                return have
            target = self.base_dir / style
            await hass.async_add_executor_job(lambda: target.mkdir(parents=True, exist_ok=True))
            for key, url in missing.items():
                try:
                    have[key] = await self._fetch(hass, url, target, key)
                    _LOGGER.info("Downloaded ezan %s/%s", style, key)
                except Exception as err:  # noqa: BLE001 - keep going with what we have
                    _LOGGER.warning("Could not download ezan %s/%s from %s: %s", style, key, url, err)
            manifest = json.dumps(have, indent=1)
            await hass.async_add_executor_job(self._manifest_path(style).write_text, manifest)
            return have

    async def _fetch(self, hass, url: str, target: Path, key: str) -> str:
        ext = Path(url.split("?")[0]).suffix.lower() or ".mp3"
        raw = target / f".{key}.download{ext}"
        async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            resp.raise_for_status()
            data = await resp.read()
        if len(data) < 10_000:
            raise ValueError(f"suspiciously small file ({len(data)} bytes)")
        await hass.async_add_executor_job(raw.write_bytes, data)
        out_name = f"{key}.mp3"
        if self._ffmpeg:
            out = target / out_name
            proc = await asyncio.create_subprocess_exec(
                self._ffmpeg, "-v", "error", "-y", "-i", str(raw), "-map_metadata", "-1", "-vn",
                "-ac", "1", "-ar", "44100", "-af",
                "silenceremove=start_periods=1:start_threshold=-45dB,"
                "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:d=0.5,"
                "areverse,afade=t=in:d=2,areverse",
                "-b:a", "96k", str(out),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
            _, err = await proc.communicate()
            if proc.returncode == 0:
                await hass.async_add_executor_job(raw.unlink)
                return out_name
            _LOGGER.warning("ffmpeg failed for %s (%s); keeping the original file", url, err.decode()[-300:])
        out_name = f"{key}{ext}"
        await hass.async_add_executor_job(raw.rename, target / out_name)
        return out_name

    async def url_for(self, hass, style: str, prayer: str, options: dict) -> str | None:
        """URL to play for `prayer` in `style` (downloading on first use)."""
        if style == STYLE_RANDOM:
            style = random.choice(list(CATALOG))
        if style == STYLE_CUSTOM:
            fajr = (options.get(CONF_CUSTOM_FAJR_URL) or "").strip()
            adhan = (options.get(CONF_CUSTOM_ADHAN_URL) or "").strip()
            url = (fajr or adhan) if prayer == "fajr" else adhan
            if url:
                return url
            _LOGGER.warning("Style is 'custom' but no custom URL is set; using the default style")
            style = "turkish_sehitoglu"
        if style not in CATALOG:
            style = "turkish_sehitoglu"
        files = await self.ensure(hass, style)
        key = CATALOG[style].key_for(prayer)
        if key and key in files:
            return f"{AUDIO_URL}/{style}/{files[key]}"
        if prayer == "fajr":
            fb = await self.ensure(hass, FALLBACK_FAJR_STYLE)
            if "fajr" in fb:
                return f"{AUDIO_URL}/{FALLBACK_FAJR_STYLE}/{fb['fajr']}"
        # Last resort: any downloaded adhan of this style.
        for k in ("adhan", *PRAYERS):
            if k in files:
                return f"{AUDIO_URL}/{style}/{files[k]}"
        return None
