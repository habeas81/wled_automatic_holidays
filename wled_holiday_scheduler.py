#!/usr/bin/env python3
"""
WLED holiday light scheduler -- no Home Assistant, no extra packages (Python 3.8+).

How it works
  * Each day it works out tonight's plan: which preset, the sunset time to turn
    on, and the (next-day) sunrise + 60 min time to turn off.
  * By day it wakes once an hour just to compare the clock (no network traffic).
    At sunset - 59 min it starts waking every 15 minutes (and checks the
    controller is reachable) until sunrise + 1 hour, then returns to hourly.
    It also wakes exactly at the on and off times.
  * On start-up (including after a PC reboot) it applies whatever the lights
    should be doing right now, so an outage heals itself.
  * If the controller is unreachable it logs it and retries with back-off.
  * It runs under a small supervisor: if the worker CRASHES it is restarted;
    if you deliberately stop it (--stop, stop_lights.bat, or Ctrl+C in a console)
    it stays stopped until you start it again or the PC reboots.

Usage
  python wled_holiday_scheduler.py            run (supervisor + worker; what the PC runs at boot)
  python wled_holiday_scheduler.py --stop     stop it cleanly, no auto-restart
  python wled_holiday_scheduler.py --status   show tonight's plan and exit
  python wled_holiday_scheduler.py --show 2027-01-01 2027-12-31    year schedule
  python wled_holiday_scheduler.py --once --dry-run                apply-once preview
  python wled_holiday_scheduler.py --reload   re-read wled_schedule.ini right now (no restart needed)
  python wled_holiday_scheduler.py --check    validate wled_schedule.ini and exit
  python wled_holiday_scheduler.py --setup    FIRST RUN: fill in the .ini, back up your controller, add these presets to free slots
  python wled_holiday_scheduler.py --write-config   create a fresh wled_schedule.ini (never overwrites)

Configuration
  Everything you would want to change -- controller address, location, on/off offsets, which
  preset slot each holiday uses, every holiday window, the special seasons (Thanksgiving,
  Christmas, ...), OU game dates, hand-offs -- lives in wled_schedule.ini next to this script.
  Edit it any time: the running scheduler notices the change at its next wake-up (or immediately
  with --reload). A bad edit is logged and ignored; the last good settings stay in force.
  The values below are only the built-in defaults used if the file is missing.
"""
import argparse
import configparser
import datetime as dt
import functools
import json
import logging
import logging.handlers
import math
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request

# ================================================================ SETTINGS
WLED_HOST = ""                    # your controller's IP or hostname -- set it in wled_schedule.ini [controller]
LAT, LON = None, None             # your location -- set it in wled_schedule.ini [location]
TZ_NAME = ""                      # e.g. America/Chicago; blank = use this computer's own timezone
SUNSET_OFFSET_MIN = 0             # lights ON this many minutes after sunset (negative = earlier)
SUNRISE_OFFSET_MIN = 60           # lights OFF this many minutes after sunrise
DAYS_BEFORE, DAYS_AFTER = 14, 7   # holiday window: 2 weeks before, 1 week after
# Per-holiday windows in evening dates: (nights before, nights after) the holiday.
# Major holidays (4th of July, Memorial Day, Halloween) use the full default of
# DAYS_BEFORE/DAYS_AFTER (2 weeks before .. 1 week after).
# Minor holidays use 1 week before .. the evening after, so the last lit night ends at
# sunrise(+offset) of the 2nd day after the holiday. Birthdays / Valentine's are shorter still.
MINOR_WINDOW = (7, 1)
WINDOWS = {
    "STPATRICKS": MINOR_WINDOW, "EASTER": MINOR_WINDOW, "ARMEDFORCES": MINOR_WINDOW,
    "FLAG": MINOR_WINDOW, "LABOR": MINOR_WINDOW, "COLUMBUS": MINOR_WINDOW,
    "VALENTINES": (1, 0), "USAF": (1, 0),
    "MLK": (1, 0), "PRESIDENTS": (1, 0), "PATRIOT": (1, 0), "CINCO": (1, 0), "MARDIGRAS": (1, 0),
    "GROUNDHOG": (1, 0), "SUPERBOWL": (1, 0),
    "CAPITALS": (0, 0),                         # game nights only
}

PRE_ROLL_MIN = 59                 # start the fast cadence this long before lights-on (sunset)
SLOW_SECONDS = 3600               # daytime / dark-season wake interval (clock check only)
FAST_SECONDS = 900                # evening-to-morning wake interval (clock check + controller check)
HEALTH_GAP_SECONDS = 600          # never hit the controller more often than this
MAX_BACKOFF_SECONDS = 300         # longest retry delay when the controller is unreachable
SET_BOOT_PRESET = True            # also make tonight's preset the controller's power-on default
HTTP_TIMEOUT = 5                  # seconds; a dead controller can never hang the script
LOCK_PORT = 47831                 # local-only port used to prevent two copies running
CONFIG_POLL_SECONDS = 0           # >0: also check the .ini for edits this often (0 = at normal wakes / --reload)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "wled_schedule.ini")
LOG_FILE = os.path.join(BASE_DIR, "wled_scheduler.log")
STOP_FLAG = os.path.join(BASE_DIR, "stop.flag")

# WLED preset slots (slot 1 = Chase 3 is untouched and unused here)
PRESET = {
    "OU": 2, "THANKSGIVING": 3,
    "VALENTINES": 4, "STPATRICKS": 5, "ARMEDFORCES": 6, "MEMORIAL": 7,
    "FLAG": 8, "JULY4": 9, "LABOR": 10, "COLUMBUS": 11, "HALLOWEEN": 12,
    "VETERANS": 13, "CHRISTMAS": 14, "NEWYEAR": 15, "EASTER": 18,
    "USAF": 27, "USMC": 28,
    "MLK": 62, "PRESIDENTS": 63, "PATRIOT": 64, "CINCO": 65, "MARDIGRAS": 66,
    "GROUNDHOG": 67, "SUPERBOWL": 68, "CAPITALS": 69, "BIRTHDAY": 70,
}

# ---- Special seasons, checked in this order after OU (first match wins).
# Each is (preset name, first evening, last evening); dates are MM-DD, "thanksgiving" or any
# holiday name, optionally +/- days (e.g. thanksgiving+1 = Black Friday).
SEASONS = [
    ("USMC", "11-09", "11-10"),                 # Marine Corps birthday: night before + the day
    ("VETERANS", "11-11", "11-11"),
    ("THANKSGIVING", "11-01", "thanksgiving"),  # Nov 1 -> Thanksgiving night (off Friday morning)
    ("CHRISTMAS", "thanksgiving+1", "12-28"),   # Black Friday night -> Dec 28 night
    ("NEWYEAR", "12-29", "01-02"),              # Dec 29 -> Jan 2 night
]
# name -> "MM-DD", "n,weekday,month" (e.g. "3,sat,5"), or an explicit list of YYYY-MM-DD dates
CUSTOM_HOLIDAYS = {
    "SUPERBOWL": "2027-02-14, 2028-02-13",       # Super Bowl LXI / LXII (add each year's date when announced)
    "CAPITALS": "",                              # your favourite team's game nights (key name is historical) - add YYYY-MM-DD dates
}
# One-off special events, checked BEFORE everything else (even OU): name -> (first evening, last evening), YYYY-MM-DD
EVENTS = []                       # e.g. ("MYEVENT", "2027-06-04", "2027-06-06") -- normally set in the [events] section of the .ini
BIRTHDAYS = {}                    # person -> "MM-DD"; each gets a 2-night window and the BIRTHDAY preset

# ---- "OU" = game-day look for your home team (name is historical; works for any team)
OU_ENABLED = False
OU_EXEMPT = {(9, 11), (9, 18), (10, 31), (11, 10), (11, 11), (12, 24), (12, 25), (12, 31)}   # actual holiday days OU must not override
OU_FALLBACK_SATURDAYS = False     # for a year with no dates listed: every Saturday, late Aug .. early Dec
OU_GAMES = {}                     # e.g. {2027: {(9, 4), (9, 11)}} -- normally set as games_YYYY lines in the .ini
OU_EXTRA_DATES = set()            # e.g. {dt.date(2026, 12, 5)} for playoff / bowl / SEC Championship nights

# ---- Mid-night hand-offs: on the night that begins on this evening date, switch presets at SWITCH_TIME
SWITCH_TIME = dt.time(0, 1)
MIDNIGHT_SWITCH = {(11, 10): "VETERANS"}   # Marine Corps birthday night -> Veterans Day at 12:01 AM

# ======================================================== TIME / SUN MATH
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(TZ_NAME)
except Exception:                  # e.g. Windows without tzdata: use the PC's timezone
    TZ = None

log = logging.getLogger("wled")


def to_local(d):
    return d.astimezone(TZ) if TZ else d.astimezone()


def localize(naive):
    return naive.replace(tzinfo=TZ) if TZ else naive.astimezone()


def _jd_to_dt(jd):
    return dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=jd - 2440587.5)


@functools.lru_cache(maxsize=1024)
def sun_times(day):
    """(sunrise, sunset) as local aware datetimes for a local calendar date.
    NOAA/Wikipedia sunrise equation; accurate to about a minute."""
    lw = LON  # east-positive; solar noon = n - lon/360
    n = math.ceil((day.toordinal() + 1721424.5) - 2451545.0 + 0.0008)
    jstar = n + 0.0009 - lw / 360.0
    m = (357.5291 + 0.98560028 * jstar) % 360
    mr = math.radians(m)
    c = 1.9148 * math.sin(mr) + 0.02 * math.sin(2 * mr) + 0.0003 * math.sin(3 * mr)
    lam = math.radians((m + c + 180 + 102.9372) % 360)
    jt = 2451545.0 + jstar + 0.0053 * math.sin(mr) - 0.0069 * math.sin(2 * lam)
    sin_d = math.sin(lam) * math.sin(math.radians(23.4397))
    cos_d = math.cos(math.asin(sin_d))
    phi = math.radians(LAT)
    cos_w = (math.sin(math.radians(-0.833)) - math.sin(phi) * sin_d) / (math.cos(phi) * cos_d)
    w = math.degrees(math.acos(max(-1.0, min(1.0, cos_w))))
    return to_local(_jd_to_dt(jt - w / 360)), to_local(_jd_to_dt(jt + w / 360))


def window(e):
    """(lights_on, lights_off) for the night that begins on evening date e."""
    on = sun_times(e)[1] + dt.timedelta(minutes=SUNSET_OFFSET_MIN)
    off = sun_times(e + dt.timedelta(days=1))[0] + dt.timedelta(minutes=SUNRISE_OFFSET_MIN)
    return on, off


# ============================================================== HOLIDAYS
def nth_weekday(year, month, weekday, n):
    """n-th given weekday (Mon=0) of a month."""
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def last_weekday(year, month, weekday):
    d = dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def thanksgiving(y):
    return nth_weekday(y, 11, 3, 4)             # 4th Thursday of November


def easter(y):
    """Western (Gregorian) Easter Sunday - anonymous Gregorian algorithm."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * l) // 433
    month = (h + l - 7 * m + 90) // 25
    day = (h + l - 7 * m + 33 * month + 19) % 32
    return dt.date(y, month, day)


WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def custom_date(spec, y):
    """Date of a custom holiday in year y. spec: "MM-DD"  or  "n,weekday,month" (n = 1..5 or last)."""
    spec = spec.strip().lower()
    if not spec:
        return None
    if re.search(r"\d{4}-\d{1,2}-\d{1,2}", spec):               # explicit dates: only the year asked for
        for tok in re.split(r"[,\s]+", spec):
            if tok:
                d = dt.date.fromisoformat(tok)
                if d.year == y:
                    return d
        return None
    if re.fullmatch(r"\d{1,2}-\d{1,2}", spec):
        m, d = map(int, spec.split("-"))
        return dt.date(y, m, d)
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) == 3 and parts[1][:3] in WEEKDAYS and parts[2].isdigit():
        wd, month = WEEKDAYS[parts[1][:3]], int(parts[2])
        return last_weekday(y, month, wd) if parts[0] == "last" else nth_weekday(y, month, wd, int(parts[0]))
    raise ValueError(f"bad date rule {spec!r} (use MM-DD or n,weekday,month e.g. 3,sat,5)")


def window_holidays(y):
    """Dates of every holiday that gets a window (built-in + custom)."""
    h = {
        "VALENTINES": dt.date(y, 2, 14),
        "STPATRICKS": dt.date(y, 3, 17),
        "EASTER": easter(y),
        "USAF": dt.date(y, 9, 18),               # Air Force birthday
        "ARMEDFORCES": nth_weekday(y, 5, 5, 3),  # 3rd Saturday of May
        "MEMORIAL": last_weekday(y, 5, 0),       # last Monday of May
        "FLAG": dt.date(y, 6, 14),
        "MLK": nth_weekday(y, 1, 0, 3),          # 3rd Monday of January
        "PRESIDENTS": nth_weekday(y, 2, 0, 3),   # 3rd Monday of February
        "GROUNDHOG": dt.date(y, 2, 2),
        "MARDIGRAS": easter(y) - dt.timedelta(days=47),
        "CINCO": dt.date(y, 5, 5),
        "PATRIOT": dt.date(y, 9, 11),
        "JULY4": dt.date(y, 7, 4),
        "LABOR": nth_weekday(y, 9, 0, 1),        # 1st Monday of September
        "COLUMBUS": nth_weekday(y, 10, 0, 2),    # 2nd Monday of October
        "HALLOWEEN": dt.date(y, 10, 31),
    }
    for name, spec in CUSTOM_HOLIDAYS.items():
        if re.search(r"\d{4}-\d{1,2}-\d{1,2}", spec):               # explicit list: every date in this year
            days = sorted({dt.date.fromisoformat(t) for t in re.split(r"[,\s]+", spec.strip()) if t})
            for i, d in enumerate(x for x in days if x.year == y):
                h[name if i == 0 else f"{name}#{i}"] = d
        else:
            d = custom_date(spec, y)
            if d is not None:
                h[name] = d
    return h


def base_name(name):
    return name.split("#")[0]                    # "CAPITALS#2" (2nd date in a year) -> "CAPITALS"


def window_for(name):
    return WINDOWS.get(base_name(name), (DAYS_BEFORE, DAYS_AFTER))


def resolve_date(expr, y):
    """'MM-DD', 'thanksgiving', or a holiday name, optionally +/- days -> date in year y."""
    m = re.fullmatch(r"\s*(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}|[a-z_][a-z0-9_]*)\s*(?:([+-])\s*(\d+))?\s*", expr.lower())
    if not m:
        raise ValueError(f"bad date {expr!r}")
    base, sign, n = m.groups()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", base):
        day = dt.date.fromisoformat(base)
    elif re.fullmatch(r"\d{1,2}-\d{1,2}", base):
        mo, d = map(int, base.split("-"))
        day = dt.date(y, mo, d)
    elif base == "thanksgiving":
        day = thanksgiving(y)
    else:
        hol = window_holidays(y)
        if base.upper() not in hol:
            raise ValueError(f"unknown date name {base!r}")
        day = hol[base.upper()]
    if n:
        day += dt.timedelta(days=int(n) * (1 if sign == "+" else -1))
    return day


def in_season(e, start, end):
    for y0 in (e.year - 1, e.year):
        s_, e_ = resolve_date(start, y0), resolve_date(end, y0)
        if e_ < s_:
            e_ = resolve_date(end, y0 + 1)
        if s_ <= e <= e_:
            return True
    return False


def ou_exempt(d):
    """Actual holiday days OU must NOT override."""
    if (d.month, d.day) in OU_EXEMPT:
        return True
    for name, spec in CUSTOM_HOLIDAYS.items():                      # family birthdays count as actual holiday days
        if name.startswith("BDAY_") and spec == f"{d.month:02d}-{d.day:02d}":
            return True
    return False


def ou_game_night(e):
    if e in OU_EXTRA_DATES:
        return True
    games = OU_GAMES.get(e.year)
    if games is not None:
        return (e.month, e.day) in games
    if not OU_FALLBACK_SATURDAYS:
        return False
    # Fallback when the year's dates are unknown: every Saturday, last Sat of Aug .. 1st Sat of Dec
    start, end = last_weekday(e.year, 8, 5), nth_weekday(e.year, 12, 5, 1)
    return e.weekday() == 5 and start <= e <= end


def preset_for_evening(e):
    """Preset name for the night that BEGINS on evening date e (None = lights dark)."""
    for name, start, end in EVENTS:                                 # 0. one-off events beat everything
        if in_season(e, start, end):
            return name
    if OU_ENABLED and ou_game_night(e) and not ou_exempt(e):       # 1. OU game night
        return "OU"
    for name, start, end in SEASONS:                                # 2. special seasons, in file order
        if in_season(e, start, end):
            return name
    hits = {}                                                       # 3. holiday windows
    for yy in (e.year - 1, e.year, e.year + 1):
        for name, d in window_holidays(yy).items():
            delta = (d - e).days
            before, after = window_for(name)
            if -after <= delta <= before and (name not in hits or abs(delta) < abs(hits[name])):
                hits[name] = delta
    hits = {n: dl for n, dl in hits.items()}
    if "STPATRICKS" in hits and "EASTER" in hits:                   #    St. Patrick's night itself stays St. Patrick's;
        return "STPATRICKS" if hits["STPATRICKS"] >= 0 else "EASTER"  # Easter takes over the next evening
    best = None                                                     #    otherwise nearest wins, ties to the upcoming one
    for name, delta in hits.items():
        # nearest wins; a tie goes to the upcoming holiday; an explicit-date event or birthday wins
        # ties only on its own day
        key = (abs(delta), 0 if delta > 0 else 1, 0 if (base_name(name) in CUSTOM_HOLIDAYS and delta == 0) else 1)
        if best is None or key < best[0]:
            best = (key, base_name(name))
    return best[1] if best else None


# ============================================================== PLANNING
def switch_at(e):
    """(datetime, preset) of the mid-night hand-off for evening e, or None."""
    name = MIDNIGHT_SWITCH.get((e.month, e.day))
    if not name or not preset_for_evening(e):
        return None
    when = dt.datetime.combine(e + dt.timedelta(days=1), SWITCH_TIME)
    return localize(when), name


def plan(now):
    """What the lights should be doing at `now`: (preset or None, next boundary time)."""
    today = now.date()
    for e in (today - dt.timedelta(days=1), today):                 # inside a lit window?
        p = preset_for_evening(e)
        if p:
            on, off = window(e)
            if on <= now < off:
                sw = switch_at(e)
                if sw and sw[1] != p:
                    return (sw[1], off) if now >= sw[0] else (p, sw[0])
                return p, off
    for k in range(0, 400):                                         # dark: when does the next one start?
        e = today + dt.timedelta(days=k)
        if preset_for_evening(e):
            on, _ = window(e)
            if on > now:
                return None, on
    return None, now + dt.timedelta(days=1)


def next_wake(now):
    """(fast, wake_time).
    fast=True  from (lights-on - PRE_ROLL_MIN) until lights-off on an evening that has a preset:
               wake every FAST_SECONDS, and exactly at lights-on and lights-off.
    fast=False otherwise: wake every SLOW_SECONDS, but never sleep past the start of the next fast phase."""
    today = now.date()
    next_start = None
    for e in (today - dt.timedelta(days=1), today, today + dt.timedelta(days=1)):
        if not preset_for_evening(e):
            continue
        on, off = window(e)
        start = on - dt.timedelta(minutes=PRE_ROLL_MIN)
        if start <= now < off:
            wake = now + dt.timedelta(seconds=FAST_SECONDS)
            sw = switch_at(e)
            for b in (on, off) + ((sw[0],) if sw else ()):
                if b > now:
                    wake = min(wake, b)
            return True, wake
        if start > now and (next_start is None or start < next_start):
            next_start = start
    wake = now + dt.timedelta(seconds=SLOW_SECONDS)
    if next_start is not None:
        wake = min(wake, next_start)
    return False, wake


# ================================================================ WLED API
def wled(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"http://{WLED_HOST}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return json.loads(r.read().decode())


def apply(name, dry=False):
    # "on": True matters: playlist presets do not carry an "on" flag, and WLED ignores a re-applied preset
    # that is already the active one, so a bare {"ps": N} could leave the lights OFF after a morning shut-off.
    payload = {"on": False} if name is None else {"on": True, "ps": PRESET[name]}
    log.info("Applying %s %s%s", name or "OFF", payload, " (dry run)" if dry else "")
    if not dry:
        wled("/json/state", payload)
        set_boot(name)


def set_boot(name):
    """Make the preset we just applied the controller's power-on default (or 'off' by day), so after a
    power loss or reboot it comes back correct by itself, before the scheduler's next check.
    Only writes when the value actually changes (WLED stores this in flash). Never raises."""
    if not SET_BOOT_PRESET:
        return
    try:
        want = {"ps": PRESET[name] if name else 0, "on": name is not None}
        have = wled("/json/cfg").get("def", {})
        if have.get("ps") == want["ps"] and bool(have.get("on")) == want["on"]:
            return
        wled("/json/cfg", {"def": want})
        log.info("Controller power-on default set to %s (preset %s, %s)", name or "OFF", want["ps"],
                 "on" if want["on"] else "off")
    except Exception as ex:
        log.warning("Could not set the controller's power-on default (%s); the scheduler still re-applies on reboot", ex)


# ============================================================ CONFIG FILE
KNOWN_FIXED = {"OU", "THANKSGIVING", "CHRISTMAS", "NEWYEAR", "VETERANS", "USMC"}


def _ints(text, what):
    try:
        return [int(x) for x in re.split(r"[,\s]+", text.strip()) if x]
    except ValueError:
        raise ValueError(f"{what}: expected whole numbers, got {text!r}")


def _md_list(text, what):
    out = set()
    for tok in re.split(r"[,\s]+", text.strip()):
        if not tok:
            continue
        m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", tok)
        if not m:
            raise ValueError(f"{what}: {tok!r} is not MM-DD")
        dt.date(2024, int(m.group(1)), int(m.group(2)))          # validates (leap year so 02-29 is allowed)
        out.add((int(m.group(1)), int(m.group(2))))
    return out


def parse_config(path):
    """Read the .ini and return a dict of settings. Raises ValueError with a readable message
    if anything is wrong; nothing is changed until the whole file has been validated."""
    cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=("#", ";"),
                                   delimiters=("=",), strict=True)
    try:
        with open(path, encoding="utf-8-sig") as fh:
            cp.read_file(fh)
    except configparser.Error as ex:
        raise ValueError(f"cannot parse file: {ex}")
    g = lambda sec, key, default=None: cp.get(sec, key, fallback=default) if cp.has_section(sec) else default
    c = {}
    try:
        c["WLED_HOST"] = (g("controller", "host", WLED_HOST) or "").strip()
        _lat, _lon = (g("location", "latitude", "") or "").strip(), (g("location", "longitude", "") or "").strip()
        c["LAT"] = float(_lat) if _lat else None
        c["LON"] = float(_lon) if _lon else None
        if (c["LAT"] is not None and not -90 <= c["LAT"] <= 90) or (c["LON"] is not None and not -180 <= c["LON"] <= 180):
            raise ValueError("latitude/longitude out of range")
        c["TZ_NAME"] = (g("location", "timezone", TZ_NAME) or "").strip()
        c["SUNSET_OFFSET_MIN"] = int(g("timing", "sunset_offset_min", SUNSET_OFFSET_MIN))
        c["SUNRISE_OFFSET_MIN"] = int(g("timing", "sunrise_offset_min", SUNRISE_OFFSET_MIN))
        c["PRE_ROLL_MIN"] = int(g("timing", "pre_roll_min", PRE_ROLL_MIN))
        c["SLOW_SECONDS"] = int(g("timing", "slow_seconds", SLOW_SECONDS))
        c["FAST_SECONDS"] = int(g("timing", "fast_seconds", FAST_SECONDS))
        c["CONFIG_POLL_SECONDS"] = int(g("timing", "config_poll_seconds", CONFIG_POLL_SECONDS))
        c["SET_BOOT_PRESET"] = str(g("controller", "set_power_on_default",
                                     "yes" if SET_BOOT_PRESET else "no")).strip().lower() in ("1", "yes", "true", "on")
        if c["FAST_SECONDS"] < 60 or c["SLOW_SECONDS"] < 60:
            raise ValueError("fast_seconds / slow_seconds must be at least 60")
        if c["CONFIG_POLL_SECONDS"] and c["CONFIG_POLL_SECONDS"] < 10:
            raise ValueError("config_poll_seconds must be 0 or at least 10")
    except (TypeError, ValueError) as ex:
        raise ValueError(f"[location]/[timing]/[controller]: {ex}")

    # presets
    presets = dict(PRESET)
    if cp.has_section("presets"):
        for k, v in cp.items("presets"):
            n = int(_ints(v, f"[presets] {k}")[0])
            if not 1 <= n <= 250:
                raise ValueError(f"[presets] {k}: slot must be 1-250")
            presets[k.upper()] = n
    for person in birthdays_names(cp):
        presets["BDAY_" + person.upper()] = presets.get("BIRTHDAY", PRESET["BIRTHDAY"])
    c["PRESET"] = presets

    # custom holidays
    custom = dict(CUSTOM_HOLIDAYS) if not cp.has_section("custom_holidays") else {}
    if cp.has_section("custom_holidays"):
        for k, v in cp.items("custom_holidays"):
            custom_date(v, 2026)                                   # validate
            custom[k.upper()] = v.strip()
    # birthdays: each person gets a 2-night window and the shared BIRTHDAY preset
    birthdays = {} if cp.has_section("birthdays") else dict(BIRTHDAYS)
    if cp.has_section("birthdays"):
        for k, v in cp.items("birthdays"):
            (md,) = _md_list(v, f"[birthdays] {k}")
            birthdays[k] = f"{md[0]:02d}-{md[1]:02d}"
    for person, md in birthdays.items():
        custom["BDAY_" + person.upper()] = md
    c["CUSTOM_HOLIDAYS"] = custom
    # one-off events (checked before everything else)
    if cp.has_section("events"):
        events = []
        for k, v in cp.items("events"):
            parts = [p.strip() for p in v.split("..")]
            if len(parts) != 2:
                raise ValueError(f"[events] {k}: expected 'YYYY-MM-DD .. YYYY-MM-DD'")
            dt.date.fromisoformat(parts[0]); dt.date.fromisoformat(parts[1])
            events.append((k.upper(), parts[0], parts[1]))
        c["EVENTS"] = events
    else:
        c["EVENTS"] = list(EVENTS)

    # windows
    windows = {}
    default = (DAYS_BEFORE, DAYS_AFTER)
    if cp.has_section("windows"):
        for k, v in cp.items("windows"):
            nums = _ints(v, f"[windows] {k}")
            if len(nums) != 2 or min(nums) < 0:
                raise ValueError(f"[windows] {k}: expected 'nights_before, nights_after' (e.g. 7, 1)")
            if k == "default":
                default = (nums[0], nums[1])
            else:
                windows[k.upper()] = (nums[0], nums[1])
    else:
        windows = dict(WINDOWS)
    for person in birthdays_names(cp):
        windows.setdefault("BDAY_" + person.upper(), (1, 0))
    c["WINDOWS"], c["DAYS_BEFORE"], c["DAYS_AFTER"] = windows, default[0], default[1]

    # seasons (file order = priority)
    if cp.has_section("seasons"):
        seasons = []
        for k, v in cp.items("seasons"):
            parts = [p.strip() for p in v.split("..")]
            if len(parts) != 2:
                raise ValueError(f"[seasons] {k}: expected 'start .. end' (e.g. 11-01 .. thanksgiving)")
            seasons.append((k.upper(), parts[0], parts[1]))
        c["SEASONS"] = seasons
    else:
        c["SEASONS"] = list(SEASONS)

    # OU
    ou_games, ou_extra = {}, set()
    c["OU_ENABLED"] = cp.getboolean("ou", "enabled", fallback=OU_ENABLED) if cp.has_section("ou") else OU_ENABLED
    c["OU_FALLBACK_SATURDAYS"] = (cp.getboolean("ou", "fallback_every_saturday", fallback=OU_FALLBACK_SATURDAYS)
                                  if cp.has_section("ou") else OU_FALLBACK_SATURDAYS)
    if cp.has_section("ou"):
        c["OU_EXEMPT"] = _md_list(cp.get("ou", "exempt", fallback=""), "[ou] exempt") if cp.has_option("ou", "exempt") else set(OU_EXEMPT)
        for k, v in cp.items("ou"):
            if k == "extra_dates":
                for tok in re.split(r"[,\s]+", v.strip()):
                    if tok:
                        ou_extra.add(dt.date.fromisoformat(tok))
            elif re.fullmatch(r"games_\d{4}", k):
                ou_games[int(k[6:])] = _md_list(v, f"[ou] {k}")
        c["OU_GAMES"], c["OU_EXTRA_DATES"] = ou_games, ou_extra
    else:
        c["OU_EXEMPT"], c["OU_GAMES"], c["OU_EXTRA_DATES"] = set(OU_EXEMPT), dict(OU_GAMES), set(OU_EXTRA_DATES)

    # mid-night hand-offs
    sw, t = {}, SWITCH_TIME
    if cp.has_section("midnight_switch"):
        for k, v in cp.items("midnight_switch"):
            if k == "time":
                try:
                    t = dt.datetime.strptime(v.strip(), "%H:%M").time()
                except ValueError:
                    raise ValueError("[midnight_switch] time: use HH:MM, e.g. 00:01")
            else:
                (md,) = _md_list(k, "[midnight_switch]")
                sw[md] = v.strip().upper()
    else:
        sw = dict(MIDNIGHT_SWITCH)
    c["MIDNIGHT_SWITCH"], c["SWITCH_TIME"] = sw, t

    # cross-checks: every name used must be a known holiday and have a preset slot
    hol = set(window_holidays_for(c["CUSTOM_HOLIDAYS"]))
    for name in c["WINDOWS"]:
        if name not in hol:
            raise ValueError(f"[windows] {name.lower()}: unknown holiday (add it under [custom_holidays] first)")
    used = {n for n, _, _ in c["SEASONS"]} | {n for n, _, _ in c["EVENTS"]} | set(c["MIDNIGHT_SWITCH"].values()) | hol | {"OU"}
    missing = sorted(n for n in used if n not in c["PRESET"])
    if missing:
        raise ValueError("no preset slot in [presets] for: " + ", ".join(m.lower() for m in missing))
    return c


def birthdays_names(cp):
    return [k for k, _ in cp.items("birthdays")] if cp.has_section("birthdays") else list(BIRTHDAYS)


def window_holidays_for(custom):
    keys = {"VALENTINES", "STPATRICKS", "EASTER", "USAF", "ARMEDFORCES", "MEMORIAL", "FLAG",
            "JULY4", "LABOR", "COLUMBUS", "HALLOWEEN", "MLK", "PRESIDENTS", "GROUNDHOG",
            "MARDIGRAS", "CINCO", "PATRIOT"}
    return keys | set(custom)


def commit_config(c):
    """Install a validated settings dict, then sanity-check it by building a year of schedule.
    Rolls everything back if the check fails."""
    global TZ
    old = {k: globals()[k] for k in c}
    old_tz = TZ
    try:
        globals().update(c)
        try:
            TZ = ZoneInfo(TZ_NAME)
        except Exception:
            TZ = None
        sun_times.cache_clear()
        today = dt.date.today()
        for k in range(0, 400):                                    # evaluates every rule once
            preset_for_evening(today + dt.timedelta(days=k))
        for name in {preset_for_evening(today + dt.timedelta(days=k)) for k in range(0, 400)} - {None}:
            if name not in PRESET:
                raise ValueError(f"no preset slot for {name.lower()}")
    except Exception:
        globals().update(old)
        TZ = old_tz
        sun_times.cache_clear()
        raise


_cfg_state = {"mtime": None}


def load_config(force=False, announce=True):
    """Load wled_schedule.ini if it exists and has changed. Never raises: a bad file is logged and
    ignored, leaving the last good settings in force. Returns True if new settings were installed."""
    try:
        mtime = os.path.getmtime(CONFIG_FILE)
    except OSError:
        if _cfg_state["mtime"] != "missing":
            _cfg_state["mtime"] = "missing"
            if announce:
                log.info("No %s found; using the built-in defaults (run --write-config to create one)",
                         os.path.basename(CONFIG_FILE))
        return False
    if mtime == _cfg_state["mtime"] and not force:
        return False
    _cfg_state["mtime"] = mtime
    try:
        c = parse_config(CONFIG_FILE)
        commit_config(c)
    except Exception as ex:
        log.error("Ignoring %s - keeping the previous settings. Problem: %s", os.path.basename(CONFIG_FILE), ex)
        return False
    if announce:
        log.info("Loaded settings from %s", os.path.basename(CONFIG_FILE))
    return True


# =================================================================== MAIN
def acquire_lock():
    """Local-only control socket: prevents two copies and lets --stop reach the worker."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":      # lets Linux/macOS restart right after a stop (never use this on Windows)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(2)
    except OSError:
        log.error("Another copy is already running; exiting.")
        sys.exit(0)
    return s


def config_changed():
    try:
        return os.path.getmtime(CONFIG_FILE) != _cfg_state["mtime"]
    except OSError:
        return False


def wait_for_command(srv, seconds, poll=0, changed=None):
    """Sleep up to `seconds`, waking early if a local STOP command arrives. Returns 'STOP' or None.
    When run from a console, sleep in 1-second slices so Ctrl+C responds immediately on Windows
    (Python can't be interrupted inside one long socket wait there). Without a console the
    scheduler sleeps in one long wait."""
    interactive = sys.stdin is not None and sys.stdin.isatty()
    deadline = time.monotonic() + seconds
    next_poll = time.monotonic() + poll if poll else None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        slice_ = remaining
        if poll:
            slice_ = min(slice_, max(next_poll - time.monotonic(), 0.1))
        if interactive:
            slice_ = min(slice_, 1.0)
        srv.settimeout(max(slice_, 0.1))
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            if poll and changed and time.monotonic() >= next_poll:
                next_poll = time.monotonic() + poll
                if changed():
                    return "RELOAD"
            continue
        except OSError:
            time.sleep(min(max(remaining, 0), 60))
            return None
        with conn:
            conn.settimeout(2)
            try:
                data = conn.recv(64).strip().upper()
                if data == b"STOP":
                    conn.sendall(b"OK\n")
                    return "STOP"
                if data == b"RELOAD":
                    conn.sendall(b"OK\n")
                    return "RELOAD"
                conn.sendall(b"UNKNOWN\n")
            except OSError:
                pass
        return None


def fmt(t):
    return t.strftime("%a %b %d %H:%M")


def now_local(args):
    if args.now:
        return localize(dt.datetime.fromisoformat(args.now))
    return to_local(dt.datetime.now(dt.timezone.utc))


def unconfigured():
    """Return a help message if the controller address or location has not been filled in yet."""
    missing = []
    if not WLED_HOST:
        missing.append("[controller] host")
    if LAT is None or LON is None:
        missing.append("[location] latitude and longitude")
    if not missing:
        return None
    return ("Not configured yet: please fill in " + " and ".join(missing) + " in " + CONFIG_FILE +
            "\n(run --write-config first if that file does not exist), then try again.")


def run(args):
    """The worker. Exits with code 0 ONLY when deliberately stopped."""
    srv = None if args.once else acquire_lock()
    load_config(announce=True)
    log.info("Worker started (WLED %s, tz %s)", WLED_HOST, TZ_NAME if TZ else "system")
    last_applied, last_uptime, last_health = "unset", None, -1e9
    last_logged_day, last_fast, fails = None, None, 0
    reload_now = False
    while True:
        try:
            if load_config(force=reload_now):
                log.info("New settings are in effect")
            reload_now = False
            now = now_local(args)
            want, boundary = plan(now)
            slot = PRESET.get(want) if want else None
            fast, wake = next_wake(now)
            if now.date() != last_logged_day:
                last_logged_day = now.date()
                on, off = window(now.date())
                log.info("Today's plan: tonight = %s (on %s, off %s); now %s until %s",
                         preset_for_evening(now.date()) or "dark", fmt(on), fmt(off),
                         want or "OFF", fmt(boundary))
            if fast != last_fast:
                last_fast = fast
                log.info("Wake cadence: every %d min%s", (FAST_SECONDS if fast else SLOW_SECONDS) // 60,
                         "" if fast else " (clock check only)")
            need = (want, slot) != last_applied
            if not need and fast and not args.dry_run \
                    and time.monotonic() - last_health >= HEALTH_GAP_SECONDS:
                up = wled("/json/info").get("uptime")      # reachability check; reboot => re-apply
                last_health = time.monotonic()
                if last_uptime is not None and up is not None and up < last_uptime:
                    log.warning("Controller rebooted; re-applying")
                    need = True
                last_uptime = up
            if need:
                apply(want, args.dry_run)
                last_applied, fails = (want, slot), 0
                if not args.dry_run:
                    try:
                        last_uptime = wled("/json/info").get("uptime")
                        last_health = time.monotonic()
                    except Exception:
                        pass
            wait = max((wake - now).total_seconds() + 1, 2)
        except Exception as ex:                          # never die: log and retry with back-off
            fails += 1
            wait = min(30 * 2 ** min(fails - 1, 5), MAX_BACKOFF_SECONDS)
            if isinstance(ex, OSError):                  # network / controller down: one-line warning
                log.warning("WLED unreachable (%s); retry %d in %ds", ex, fails, wait)
            else:
                log.exception("Unexpected error; retry %d in %ds", fails, wait)
        if args.once:
            sys.exit(1 if fails else 0)
        cmd = wait_for_command(srv, wait, CONFIG_POLL_SECONDS, config_changed)
        if cmd == "STOP":
            log.info("Stop requested; exiting cleanly (it will not restart until you start it or the PC reboots).")
            sys.exit(0)
        if cmd == "RELOAD":
            reload_now = True


def supervise(args):
    """Runs the worker and restarts it if it CRASHES. A clean stop (exit code 0) ends everything."""
    try:
        os.remove(STOP_FLAG)                              # stale flag from a previous stop
    except OSError:
        pass
    cmd = [sys.executable, os.path.abspath(__file__), "--worker"]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.now:
        cmd += ["--now", args.now]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)    # no console window on Windows
    delay = 30
    log.info("Supervisor started")
    while True:
        started = time.monotonic()
        proc = subprocess.Popen(cmd, creationflags=flags)
        try:
            rc = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            log.info("Stopped from the keyboard.")
            return
        if rc == 0 or os.path.exists(STOP_FLAG):
            log.info("Worker stopped cleanly; supervisor exiting.")
            break
        if time.monotonic() - started > 300:              # it ran fine for a while: reset the back-off
            delay = 30
        pause, delay = delay, min(delay * 2, 300)         # 30s, 60s, 120s ... up to 5 min if it keeps crashing
        log.error("Worker crashed (exit code %s); restarting in %ds", rc, pause)
        for _ in range(pause):                            # interruptible wait
            if os.path.exists(STOP_FLAG):
                break
            time.sleep(1)
        if os.path.exists(STOP_FLAG):
            log.info("Stop requested while the worker was down; supervisor exiting.")
            break
    try:
        os.remove(STOP_FLAG)
    except OSError:
        pass


def stop_command():
    """--stop: ask the running scheduler to exit cleanly and NOT be restarted."""
    try:
        with open(STOP_FLAG, "w") as f:
            f.write("stop")
    except OSError:
        pass
    try:
        with socket.create_connection(("127.0.0.1", LOCK_PORT), timeout=3) as c:
            c.sendall(b"STOP\n")
            c.settimeout(3)
            c.recv(16)
    except OSError:
        print("The scheduler does not appear to be running.")
        return
    for _ in range(20):                                   # wait for it to actually exit
        time.sleep(0.5)
        try:
            socket.create_connection(("127.0.0.1", LOCK_PORT), timeout=1).close()
        except OSError:
            print("Scheduler stopped. It will stay stopped until you start it again or the PC reboots.")
            return
    print("Stop was requested but the scheduler is still shutting down; check wled_scheduler.log.")


def default_config_text():
    """The built-in defaults rendered as a commented wled_schedule.ini."""
    names = {"VALENTINES": "Valentine's Day, Feb 14", "STPATRICKS": "St. Patrick's Day, Mar 17",
             "EASTER": "Easter Sunday", "USAF": "Air Force birthday, Sep 18",
             "ARMEDFORCES": "Armed Forces Day, 3rd Sat of May", "MEMORIAL": "Memorial Day",
             "FLAG": "Flag Day, Jun 14", "JULY4": "4th of July", "LABOR": "Labor Day",
             "COLUMBUS": "Columbus Day", "HALLOWEEN": "Halloween, Oct 31",
             "MLK": "Martin Luther King Jr. Day, 3rd Mon of Jan", "PRESIDENTS": "Presidents Day, 3rd Mon of Feb",
             "GROUNDHOG": "Groundhog Day, Feb 2", "MARDIGRAS": "Mardi Gras (Fat Tuesday)",
             "CINCO": "Cinco de Mayo, May 5", "PATRIOT": "Patriot Day, Sep 11",
             "SUPERBOWL": "Super Bowl Sunday (dates under [custom_holidays])",
             "CAPITALS": "your team's game nights (dates under [custom_holidays])"}
    L = []
    a = L.append
    a("# WLED holiday scheduler settings.")
    a("# Edit and save any time - the running scheduler picks up changes at its next wake-up")
    a("# (or immediately with:  py wled_holiday_scheduler.py --reload).")
    a("# A mistake is logged and ignored; the previous good settings stay in force.")
    a("# Check a file without applying it:  py wled_holiday_scheduler.py --check")
    a("# Lines starting with # or ; are comments.")
    a("")
    a("[controller]")
    a("; REQUIRED: the IP address (or hostname) of your WLED controller, e.g. 192.168.1.50")
    a(f"host = {WLED_HOST}")
    a("; yes = also store tonight's preset (or 'off' by day) as the controller's power-on default, so it")
    a("; comes back correct after a power loss without waiting for the scheduler")
    a(f"set_power_on_default = {'yes' if SET_BOOT_PRESET else 'no'}")
    a("")
    a("[location]")
    a("; REQUIRED: your latitude and longitude in decimal degrees (look yourself up on any map site).")
    a("; North and East are positive; South and West are negative (the US is negative longitude).")
    a(f"latitude = {'' if LAT is None else LAT}")
    a(f"longitude = {'' if LON is None else LON}")
    a("; optional: an IANA timezone name such as America/Chicago or Europe/London; blank = this computer's timezone")
    a(f"timezone = {TZ_NAME}")
    a("")
    a("[timing]")
    a(f"sunset_offset_min = {SUNSET_OFFSET_MIN}        ; lights ON this many minutes after sunset (negative = earlier)")
    a(f"sunrise_offset_min = {SUNRISE_OFFSET_MIN}       ; lights OFF this many minutes after sunrise")
    a(f"pre_roll_min = {PRE_ROLL_MIN}             ; start the fast wake cadence this long before lights-on")
    a(f"slow_seconds = {SLOW_SECONDS}           ; daytime wake interval (clock check only)")
    a(f"fast_seconds = {FAST_SECONDS}            ; evening-to-morning wake interval")
    a("config_poll_seconds = 0        ; 0 = look for .ini edits only at normal wake-ups or --reload;")
    a("                               ; e.g. 60 = also glance at the file's date every minute (very cheap)")
    a("")
    a("[presets]")
    a("; which WLED preset slot each name uses (names are the section/holiday names below)")
    for k, v in PRESET.items():
        a(f"{k.lower()} = {v}")
    a("")
    a("[windows]")
    a("; nights_before, nights_after: how many evenings before / after the holiday date get lights.")
    a("; Lights run through sunrise (+offset) of the morning after the last lit night, so")
    a("; '7, 1' = starts 7 evenings before and the last lit night is the evening after the holiday,")
    a(";  ending at sunrise (+1h) on the 2nd morning after.")
    a("; Anything not listed uses default.")
    a(f"default = {DAYS_BEFORE}, {DAYS_AFTER}          ; major holidays: 2 weeks before .. 1 week after")
    for k in ["VALENTINES", "STPATRICKS", "EASTER", "USAF", "ARMEDFORCES", "MEMORIAL", "FLAG", "JULY4",
              "LABOR", "COLUMBUS", "HALLOWEEN", "MLK", "PRESIDENTS", "GROUNDHOG", "MARDIGRAS", "CINCO",
              "PATRIOT", "SUPERBOWL", "CAPITALS"]:
        b, af = WINDOWS.get(k, (DAYS_BEFORE, DAYS_AFTER))
        a(f"{k.lower()} = {b}, {af}".ljust(26) + f"; {names[k]}")
    a("")
    a("[custom_holidays]")
    a("; Add your own holiday: name = MM-DD   or   name = n,weekday,month  (e.g. 3,sat,5 = 3rd Saturday of May;")
    a("; use 'last' for the last one, e.g. last,mon,5)   or   name = YYYY-MM-DD, YYYY-MM-DD, ...  (explicit")
    a("; dates for things that move around, like the Super Bowl or your team's game nights).")
    a("; Then give it a slot in [presets] and (optionally) a window in [windows].")
    a("; An explicit-date event wins over other holidays on its own day.")
    for k, v in CUSTOM_HOLIDAYS.items():
        a(f"{k.lower()} = {v}")
    a("; capitals: list your team's game nights as YYYY-MM-DD, comma separated (tonight only)")
    a("")
    a("[events]")
    a("; One-off special events, checked FIRST (they even beat OU game nights).")
    a("; name = first evening .. last evening  (YYYY-MM-DD). Needs a slot in [presets]. Delete the line afterwards or leave it.")
    a(";   myevent = 2027-06-04 .. 2027-06-06       ; (needs a matching slot under [presets])")
    for n, st, en in EVENTS:
        a(f"{n.lower()} = {st} .. {en}")
    a("")
    a("[birthdays]")
    a("; person = MM-DD. Each gets the night before + the day, using the 'birthday' preset.")
    a(";   alex = 03-05")
    for p_, md in BIRTHDAYS.items():
        a(f"{p_} = {md}")
    a("")
    a("[seasons]")
    a("; Special stretches, checked in this order (first match wins; OU game nights beat all of these).")
    a("; name = first evening .. last evening.  Dates: MM-DD, thanksgiving, or any holiday name,")
    a("; optionally with +/- days (thanksgiving+1 = Black Friday). Ranges may cross New Year.")
    for n, st, en in SEASONS:
        a(f"{n.lower()} = {st} .. {en}")
    a("")
    a("[ou]")
    a("; yes = light a game-day look (the 'ou' preset) on the nights below. Name is historical; any team works.")
    a(f"enabled = {'yes' if OU_ENABLED else 'no'}")
    a("; actual holiday days that an OU game must NOT override (MM-DD)")
    a("exempt = " + ", ".join(f"{m:02d}-{d:02d}" for m, d in sorted(OU_EXEMPT)))
    a("; if a year has no games_YYYY line below, light OU on EVERY Saturday from late Aug to early Dec")
    a(f"fallback_every_saturday = {'yes' if OU_FALLBACK_SATURDAYS else 'no'}")
    a("; extra one-off OU nights (playoff / bowl / SEC Championship): YYYY-MM-DD, comma separated")
    a("extra_dates =")
    for y in sorted(OU_GAMES):
        a(f"games_{y} = " + ", ".join(f"{m:02d}-{d:02d}" for m, d in sorted(OU_GAMES[y])))
    a("; games_2027 = 08-28, 09-04     ; one line per year: MM-DD of each home/away game night")
    a("")
    a("[midnight_switch]")
    a("; On the night that BEGINS on this evening date, switch to another preset after midnight.")
    a(f"time = {SWITCH_TIME.strftime('%H:%M')}")
    for (m, d), n in MIDNIGHT_SWITCH.items():
        a(f"{m:02d}-{d:02d} = {n.lower()}            ; Marine Corps birthday night -> Veterans Day at 12:01 AM")
    a("")
    return "\n".join(L)


def reload_command():
    """--reload: validate the .ini, then tell the running scheduler to re-read it now."""
    try:
        parse_config(CONFIG_FILE)
    except Exception as ex:
        print(f"Not reloaded - {os.path.basename(CONFIG_FILE)} has a problem: {ex}")
        return
    try:
        with socket.create_connection(("127.0.0.1", LOCK_PORT), timeout=3) as c:
            c.sendall(b"RELOAD\n")
            c.settimeout(3)
            c.recv(16)
        print("Reload requested. The scheduler is applying the new settings now (see wled_scheduler.log).")
    except OSError:
        print("The scheduler does not appear to be running; the new settings load when it starts.")


def check_command():
    try:
        c = parse_config(CONFIG_FILE)
    except FileNotFoundError:
        print(f"{CONFIG_FILE} does not exist (run --write-config to create it).")
        return
    except Exception as ex:
        print(f"PROBLEM in {os.path.basename(CONFIG_FILE)}: {ex}")
        return
    print(f"{os.path.basename(CONFIG_FILE)} is valid.")


def write_config_command():
    if os.path.exists(CONFIG_FILE):
        print(f"{CONFIG_FILE} already exists; not overwriting it.")
        return
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        fh.write(default_config_text())
    print(f"Created {CONFIG_FILE}")


def status():
    now = now_local(argparse.Namespace(now=None))
    want, boundary = plan(now)
    print(f"Now: {fmt(now)}  ->  lights {want or 'OFF'} until {fmt(boundary)}")
    for k in range(0, 4):
        e = now.date() + dt.timedelta(days=k)
        on, off = window(e)
        print(f"  evening {e} {e.strftime('%a')}: {preset_for_evening(e) or 'dark':13} on {fmt(on)}  off {fmt(off)}")


def show(start, end):
    d, stop, prev = dt.date.fromisoformat(start), dt.date.fromisoformat(end), "?"
    while d <= stop:
        p = preset_for_evening(d)
        if p != prev:
            print(f"{d} {d.strftime('%a')}  {p or 'dark'}")
            prev = p
        d += dt.timedelta(days=1)


def setup_logging():
    fmt_ = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    handlers = []
    if sys.stderr is not None:                            # pythonw has no console
        handlers.append(logging.StreamHandler())
    try:
        handlers.append(logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=500_000,
                                                             backupCount=3, encoding="utf-8"))
    except OSError:
        pass
    for h in handlers:
        h.setFormatter(fmt_)
        log.addHandler(h)


# ============================================================ --setup (first-run helper)
def _ini_set(path, section, key, value):
    """Set `key = value` inside [section] of the .ini, keeping comments and layout. True if changed/found."""
    with open(path, encoding="utf-8-sig") as fh:
        lines = fh.read().split("\n")
    cur, found = None, False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1].strip().lower()
            continue
        if cur == section and s and s[0] not in ";#" and "=" in s and s.split("=", 1)[0].strip().lower() == key:
            m = re.search(r"\s+[;#].*$", ln)
            cr = "\r" if ln.endswith("\r") else ""
            lines[i] = f"{key} = {value}" + (("  " + m.group(0).strip()) if m else "") + cr
            found = True
            break
    if found:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines))
    return found


def _http(method, path, data=None, ctype=None, timeout=20):
    hdr = {"Content-Type": ctype} if ctype else {}
    req = urllib.request.Request(f"http://{WLED_HOST}{path}", data=data, method=method, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as ex:
        return ex.code, b""


def _upload(name, raw):
    b = "----wledsetup7d1c"
    body = (f'--{b}\r\nContent-Disposition: form-data; name="data"; filename="{name}"\r\n'
            f"Content-Type: application/json\r\n\r\n").encode() + raw + f"\r\n--{b}--\r\n".encode()
    st, _ = _http("POST", "/upload", body, f"multipart/form-data; boundary={b}", timeout=60)
    if st != 200:
        raise RuntimeError(f"upload of {name} failed (HTTP {st})")


def _get_json(path):
    st, raw = _http("GET", path)
    if st != 200:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        return None


def _ask(prompt, yes, default=""):
    if yes or not sys.stdin.isatty():
        return default
    try:
        return input(prompt).strip()
    except EOFError:
        return default


def setup_command(args):
    """First-run helper: fill in the .ini, back up the controller, merge these presets and palettes into
    free slots (never overwriting existing ones), and write the resulting slot numbers into the .ini."""
    global WLED_HOST
    yes, dry = args.yes, args.dry_run
    interactive = sys.stdin.isatty() and not yes
    pfile = args.presets or os.path.join(BASE_DIR, "presets.json")
    if not os.path.exists(CONFIG_FILE):
        if dry:
            print(f"(dry run: {os.path.basename(CONFIG_FILE)} does not exist yet and would be created)")
        else:
            with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
                fh.write(default_config_text())
            print(f"Created {CONFIG_FILE}")
    try:
        ours = json.load(open(pfile, encoding="utf-8"))
    except (OSError, ValueError) as ex:
        sys.exit(f"Cannot read {pfile}: {ex}")
    # ---- 1. settings
    try:
        c = parse_config(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else {"WLED_HOST": "", "LAT": None, "LON": None}
    except Exception as ex:
        sys.exit(f"Fix {os.path.basename(CONFIG_FILE)} first: {ex}")
    host = args.host or c["WLED_HOST"]
    if not host:
        host = _ask("IP address or hostname of your WLED controller (e.g. 192.168.1.50): ", yes)
    if not host:
        sys.exit("A controller address is required: use --host 192.168.1.50 or fill in [controller] host in the .ini.")
    host = host.replace("http://", "").strip("/ ")
    WLED_HOST = host
    if c["LAT"] is None or c["LON"] is None:
        txt = _ask("Your latitude, longitude (e.g. 41.88, -87.63; west/south are negative; Enter to skip): ", yes)
        try:
            la, lo = [float(x) for x in txt.replace(",", " ").split()]
            if not (-90 <= la <= 90 and -180 <= lo <= 180):
                raise ValueError
        except ValueError:
            la = lo = None
            if txt:
                print("  Could not read that; skipping. Fill in [location] in the .ini yourself.")
    else:
        la, lo = c["LAT"], c["LON"]
    # ---- 2. controller
    info = _get_json("/json/info")
    if not info:
        sys.exit(f"Cannot reach a WLED controller at http://{host}/ - check the address and that you are on the same network.")
    fs = info.get("fs", {})
    print(f"Connected to {info.get('name', 'WLED')} (WLED {info.get('ver', '?')}), {info.get('leds', {}).get('count', '?')} LEDs.")
    st, raw = _http("GET", "/presets.json")
    existing = {}
    if st == 200 and raw.strip():
        try:
            existing = json.loads(raw.decode("utf-8"))
        except ValueError:
            sys.exit("The controller's presets.json could not be read; not changing anything.")
    used = {int(k) for k, v in existing.items() if k.isdigit() and int(k) > 0 and v}
    exist_pal = {n: _get_json(f"/palette{n}.json") for n in range(10)}
    exist_pal = {n: v for n, v in exist_pal.items() if isinstance(v, dict) and "palette" in v}
    mapfile = os.path.join(BASE_DIR, "wled_setup_map.json")
    try:
        prev = json.load(open(mapfile, encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    # ---- 3. palettes
    our_pal = {}
    for n in range(10):
        p = os.path.join(BASE_DIR, f"palette{n}.json")
        if os.path.exists(p):
            our_pal[n] = json.load(open(p, encoding="utf-8"))
    palmap, pal_notes, taken = {}, [], set(exist_pal)
    for n, body in our_pal.items():
        old = prev.get("palettes", {}).get(str(n))
        if n in exist_pal and exist_pal[n] == body:
            palmap[n] = n
        elif old is not None and old in exist_pal and exist_pal[old] == body:
            palmap[n] = old
        elif n not in exist_pal:
            palmap[n] = n
            taken.add(n)
    for n in our_pal:
        if n in palmap:
            continue
        free = next((k for k in range(10) if k not in taken), None)
        if free is None:
            palmap[n] = None
            pal_notes.append(f"palette {n}: all 10 custom palette slots are in use; looks using it fall back to the built-in 'Colors Only' palette")
        else:
            palmap[n] = free
            taken.add(free)
            pal_notes.append(f"palette {n} -> your free palette slot {free}")

    def remap_pal(p):
        if isinstance(p, int) and 191 <= p <= 200 and (200 - p) in palmap:
            t = palmap[200 - p]
            return 5 if t is None else 200 - t
        return p
    # ---- 4. preset slots
    our_slots = sorted(int(k) for k in ours if k.isdigit() and int(k) > 0 and ours[k])
    assigned = {}
    for s in our_slots:                                      # re-run of an earlier setup: update our own presets in place
        t = prev.get("presets", {}).get(str(s))
        if t and str(t) in existing and existing[str(t)].get("n") == ours[str(s)].get("n"):
            assigned[s] = t
    reserved = set(assigned.values())
    for s in our_slots:
        if s not in assigned and s not in used and s not in reserved:
            assigned[s] = s
            reserved.add(s)
    for s in our_slots:
        if s not in assigned:
            t = next((k for k in range(1, 251) if k not in used and k not in reserved), None)
            if t is None:
                sys.exit("Your controller has no free preset slots left (WLED allows 250); nothing changed.")
            assigned[s] = t
            reserved.add(t)
    merged = dict(existing)
    for s in our_slots:
        p = json.loads(json.dumps(ours[str(s)]))
        for sg in p.get("seg", []):
            if "pal" in sg:
                sg["pal"] = remap_pal(sg["pal"])
        if "playlist" in p:
            p["playlist"]["ps"] = [assigned[x] for x in p["playlist"]["ps"]]
        merged[str(assigned[s])] = p
    out = json.dumps(merged, separators=(",", ":")).encode("utf-8")
    moved = {s: t for s, t in assigned.items() if s != t}
    inplace = sum(1 for s, t in assigned.items() if str(t) in existing)
    # ---- 5. plan
    print("\nPlan:")
    print(f"  {len(our_slots)} presets/playlists to add" + (f" ({inplace} of them already installed by an earlier setup and updated in place)" if inplace else "")
          + f"; your {len(used) - inplace} other presets are not touched.")
    if moved:
        sample = ", ".join(f"{s}->{t}" for s, t in list(moved.items())[:12]) + (" ..." if len(moved) > 12 else "")
        print(f"  {len(moved)} moved to free slots because yours are taken: {sample}")
    else:
        print("  every preset keeps its original slot number.")
    for n in pal_notes:
        print("  " + n)
    pal_up = [n for n, t in palmap.items() if t is not None and exist_pal.get(t) != our_pal[n]]
    print(f"  {len(pal_up)} palette file(s) to upload; the new presets.json will be {len(out) // 1024 + 1} KB.")
    room = (fs.get("t", 0) - fs.get("u", 0)) * 1024
    if fs and len(out) + 4096 > room + len(json.dumps(existing).encode()):
        print("  WARNING: the controller may not have enough free flash for this; see the Info page.")
    if palmap and not any(palmap.values()) and our_pal:
        print("  WARNING: none of the custom palettes could be installed.")
    print(f"  .ini: host = {host}" + (f", latitude/longitude = {la}, {lo}" if la is not None else "") + ", and the [presets] slot numbers.")
    if dry:
        print("\nDry run: nothing was changed.")
        return
    if not interactive and not yes:
        print("\nNot a terminal; re-run with --yes to apply.")
        return
    if interactive and _ask("\nBack up and apply this? [y/N] ", yes).lower() not in ("y", "yes"):
        print("Cancelled; nothing was changed.")
        return
    # ---- 6. backup, apply
    bdir = os.path.join(BASE_DIR, "wled_backup_" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(bdir)
    with open(os.path.join(bdir, "presets.json"), "wb") as fh:
        fh.write(raw if st == 200 else b"{}")
    for n, body in exist_pal.items():
        with open(os.path.join(bdir, f"palette{n}.json"), "w", encoding="utf-8") as fh:
            json.dump(body, fh)
    print(f"\nBacked up your controller to {bdir}")
    for n in pal_up:
        _upload(f"palette{palmap[n]}.json", json.dumps(our_pal[n], separators=(",", ":")).encode())
    _upload("presets.json", out)
    time.sleep(1)
    check = _get_json("/presets.json") or {}
    missing = [t for t in assigned.values() if str(t) not in check]
    if missing:
        print(f"WARNING: {len(missing)} presets did not show up on the controller; your backup is in {bdir}")
    else:
        print(f"Uploaded {len(our_slots)} presets and {len(pal_up)} palettes; verified on the controller.")
    # ---- 7. .ini
    _ini_set(CONFIG_FILE, "controller", "host", host)
    if la is not None:
        _ini_set(CONFIG_FILE, "location", "latitude", la)
        _ini_set(CONFIG_FILE, "location", "longitude", lo)
    for name, slot in PRESET.items():
        if slot in assigned:
            _ini_set(CONFIG_FILE, "presets", name.lower(), assigned[slot])
    with open(mapfile, "w", encoding="utf-8") as fh:
        json.dump({"presets": {str(s): t for s, t in assigned.items()},
                   "palettes": {str(n): t for n, t in palmap.items()}}, fh, indent=1)
    print(f"Updated {os.path.basename(CONFIG_FILE)}.")
    print("Reload the WLED page in your browser to see the new presets.")
    if la is None:
        print("Still to do: fill in [location] latitude and longitude in the .ini.")
    print("Next: py wled_holiday_scheduler.py --check, then --status.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop", action="store_true", help="stop the running scheduler cleanly (no auto-restart)")
    ap.add_argument("--once", action="store_true", help="apply the current state once and exit")
    ap.add_argument("--dry-run", action="store_true", help="do not talk to WLED")
    ap.add_argument("--now", help="pretend it is this local time, e.g. 2026-11-14T18:00 (testing)")
    ap.add_argument("--show", nargs=2, metavar=("START", "END"), help="print schedule changes")
    ap.add_argument("--reload", action="store_true", help="make the running scheduler re-read wled_schedule.ini now")
    ap.add_argument("--check", action="store_true", help="validate wled_schedule.ini and exit")
    ap.add_argument("--write-config", action="store_true", help="create a default wled_schedule.ini (never overwrites)")
    ap.add_argument("--status", action="store_true", help="print tonight's plan and exit")
    ap.add_argument("--setup", action="store_true", help="first-run helper: fill in the .ini, back up the controller, add the presets to free slots")
    ap.add_argument("--host", help="controller address for --setup")
    ap.add_argument("--presets", help="presets file for --setup (default presets.json next to the script)")
    ap.add_argument("--yes", action="store_true", help="--setup: apply without asking")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    setup_logging()
    try:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    except Exception:
        pass
    try:
        if a.stop:
            stop_command()
        elif a.reload:
            reload_command()
        elif a.setup:
            setup_command(a)
        elif a.check:
            check_command()
        elif a.write_config:
            write_config_command()
        else:
            load_config(announce=False)
            problem = unconfigured()
            if problem:
                print(problem)
                log.error(problem.splitlines()[0])
                sys.exit(2)
            if a.show:
                show(*a.show)
            elif a.status:
                status()
            elif a.worker or a.once:
                run(a)
            else:
                supervise(a)
    except KeyboardInterrupt:
        log.info("Stopped from the keyboard.")
        sys.exit(0)
