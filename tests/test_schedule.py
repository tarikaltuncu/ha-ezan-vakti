"""Schedule math tests. Loads const.py/schedule.py without importing Home Assistant."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types

PKG = Path(__file__).parents[1] / "custom_components" / "ezan_vakti"
pkg = types.ModuleType("ev")
pkg.__path__ = [str(PKG)]
sys.modules["ev"] = pkg
for name in ("const", "schedule"):
    spec = importlib.util.spec_from_file_location(f"ev.{name}", PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"ev.{name}"] = mod
    spec.loader.exec_module(mod)
schedule = sys.modules["ev.schedule"]

TZ = timezone(timedelta(hours=3))
DAY = date(2026, 11, 11)
ROW = {"imsak": "06:12", "sunrise": "07:39", "dhuhr": "12:53", "asr": "15:32",
       "maghrib": "17:57", "isha": "19:19", "hijri": "2 Cemaziyelahir 1448"}
RAMADAN = {**ROW, "hijri": "5 Ramazan 1448"}
DAYS = {"2026-11-11": ROW, "2026-11-12": {**ROW, "imsak": "06:13", "sunrise": "07:40"}}


def at(h, m, day=DAY):
    return datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)


def times(row=ROW, **kw):
    kw = {"fajr_offset": 15, "fasting": False, "ramadan_auto": True, **kw}
    return schedule.ezan_times(DAY, row, TZ, **kw)


def test_fajr_is_offset_before_sunrise():
    assert times()["fajr"] == at(7, 24)


def test_fajr_never_before_imsak():
    assert times(fajr_offset=120)["fajr"] == at(6, 12)


def test_fasting_switch_puts_fajr_at_imsak():
    assert times(fasting=True)["fajr"] == at(6, 12)


def test_ramadan_auto():
    assert times(RAMADAN)["fajr"] == at(6, 12)
    assert times(RAMADAN, ramadan_auto=False)["fajr"] == at(7, 24)


def test_no_ezan_at_imsak_or_sunrise():
    assert set(times()) == {"fajr", "dhuhr", "asr", "maghrib", "isha"}


def test_next_ezan_today_and_rollover():
    kw = {"fajr_offset": 15, "fasting": False, "ramadan_auto": True}
    assert schedule.next_ezan(at(10, 0), DAYS, TZ, **kw) == ("dhuhr", at(12, 53))
    assert schedule.next_ezan(at(12, 53), DAYS, TZ, **kw) == ("asr", at(15, 32))
    nxt = schedule.next_ezan(at(20, 0), DAYS, TZ, **kw)
    assert nxt == ("fajr", at(7, 25, date(2026, 11, 12)))


def test_next_ezan_respects_enabled_prayers():
    kw = {"fajr_offset": 15, "fasting": False, "ramadan_auto": True}
    assert schedule.next_ezan(at(10, 0), DAYS, TZ, prayers=["maghrib"], **kw) == ("maghrib", at(17, 57))
    assert schedule.next_ezan(at(10, 0), DAYS, TZ, prayers=[], **kw) is None
