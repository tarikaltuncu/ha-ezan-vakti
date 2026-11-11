"""Pure schedule math (no Home Assistant imports, so it can be unit-tested directly)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, tzinfo

from .const import PRAYERS, VAKITS


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")[:2]
    return time(int(hour), int(minute))


def is_ramadan(row: dict[str, str]) -> bool:
    """Diyanet's Hijri month names are Turkish ("Ramazan") for every country."""
    return "ramazan" in (row.get("hijri") or "").lower()


def is_fasting(row: dict[str, str], fasting: bool, ramadan_auto: bool) -> bool:
    return fasting or (ramadan_auto and is_ramadan(row))


def vakit_times(day: date, row: dict[str, str], tz: tzinfo) -> dict[str, datetime]:
    """The six Diyanet vakits of a day as aware datetimes."""
    return {k: datetime.combine(day, parse_hhmm(row[k]), tz) for k in VAKITS}


def ezan_times(
    day: date,
    row: dict[str, str],
    tz: tzinfo,
    *,
    fajr_offset: int,
    fasting: bool,
    ramadan_auto: bool,
) -> dict[str, datetime]:
    """The five ezan times of a day.

    Fajr (Sabah) is `fajr_offset` minutes before sunrise, but never before İmsak, so it
    wakes you in time to pray before the sun rises. On fasting days (manual switch, or
    Ramadan when `ramadan_auto`) it is exactly at İmsak.
    """
    v = vakit_times(day, row, tz)
    if is_fasting(row, fasting, ramadan_auto):
        fajr = v["imsak"]
    else:
        fajr = max(v["imsak"], v["sunrise"] - timedelta(minutes=fajr_offset))
    return {
        "fajr": fajr,
        "dhuhr": v["dhuhr"],
        "asr": v["asr"],
        "maghrib": v["maghrib"],
        "isha": v["isha"],
    }


def next_ezan(
    now: datetime,
    days: dict[str, dict[str, str]],
    tz: tzinfo,
    *,
    fajr_offset: int,
    fasting: bool,
    ramadan_auto: bool,
    prayers: list[str] | tuple[str, ...] = PRAYERS,
) -> tuple[str, datetime] | None:
    """(prayer, when) of the first enabled ezan strictly after `now`, looking 2 days ahead."""
    today = now.astimezone(tz).date()
    for offset in range(3):
        day = today + timedelta(days=offset)
        row = days.get(day.isoformat())
        if not row:
            continue
        times = ezan_times(
            day, row, tz, fajr_offset=fajr_offset, fasting=fasting, ramadan_auto=ramadan_auto
        )
        for prayer in PRAYERS:
            if prayer in prayers and times[prayer] > now:
                return prayer, times[prayer]
    return None
