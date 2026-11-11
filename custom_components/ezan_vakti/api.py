"""Client for https://ezanvakti.emushaf.net (Diyanet prayer times for every country)."""

from __future__ import annotations

from typing import Any

import aiohttp

from .const import API_BASE, API_VAKIT_KEYS


class EzanVaktiApiError(Exception):
    """The prayer-times API could not be reached or returned bad data."""


class EzanVaktiApi:
    """Tiny async client. Endpoints: /ulkeler, /sehirler/{id}, /ilceler/{id}, /vakitler/{id}."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, path: str) -> Any:
        try:
            async with self._session.get(
                f"{API_BASE}{path}", timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    raise EzanVaktiApiError(f"{path}: HTTP {resp.status}")
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise EzanVaktiApiError(f"{path}: {err}") from err

    async def countries(self) -> dict[str, str]:
        """{id: name}, English names."""
        data = await self._get("/ulkeler")
        return {d["UlkeID"]: d.get("UlkeAdiEn") or d["UlkeAdi"] for d in data}

    async def cities(self, country_id: str) -> dict[str, str]:
        data = await self._get(f"/sehirler/{country_id}")
        return {d["SehirID"]: d.get("SehirAdiEn") or d["SehirAdi"] for d in data}

    async def districts(self, city_id: str) -> dict[str, str]:
        data = await self._get(f"/ilceler/{city_id}")
        return {d["IlceID"]: d.get("IlceAdiEn") or d["IlceAdi"] for d in data}

    async def times(self, district_id: str) -> dict[str, dict[str, str]]:
        """~32 days (3 days back … +4 weeks): {"YYYY-MM-DD": {vakit: "HH:MM", ..., "hijri": str}}.

        Times are local wall-clock times for the district. The API's ISO date carries
        Turkey's offset regardless of country, so only the date part is used.
        """
        data = await self._get(f"/vakitler/{district_id}")
        if not isinstance(data, list) or not data:
            raise EzanVaktiApiError("vakitler: empty response")
        out: dict[str, dict[str, str]] = {}
        for row in data:
            day, month, year = row["MiladiTarihKisa"].split(".")
            day_key = f"{year}-{month}-{day}"
            out[day_key] = {k: row[api_key] for k, api_key in API_VAKIT_KEYS.items()}
            out[day_key]["hijri"] = row.get("HicriTarihUzun") or ""
        return out
