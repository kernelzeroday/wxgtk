"""Convenience wrapper around the raw Open-Meteo responses."""

from datetime import datetime, timedelta, timezone
import time

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


def _zone(name, offset):
    if name and ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    return timezone(timedelta(seconds=offset or 0))


class Weather:
    def __init__(self, raw):
        self.raw = raw
        f = raw["forecast"]
        self.forecast = f
        self.tz = _zone(f.get("timezone"), f.get("utc_offset_seconds", 0))
        self.tz_abbr = f.get("timezone_abbreviation", "")
        self.current = f.get("current") or {}
        self.hourly = f.get("hourly") or {}
        self.daily = f.get("daily") or {}
        self.m15 = f.get("minutely_15") or {}
        self.air = raw.get("air")
        self.fetched = raw.get("fetched", 0)

    # ---- time helpers -------------------------------------------------
    def local(self, ts):
        return datetime.fromtimestamp(ts, self.tz)

    def now(self):
        return time.time()

    @staticmethod
    def _index_at(times, t):
        idx = 0
        for i, ts in enumerate(times):
            if ts <= t:
                idx = i
            else:
                break
        return idx

    def hour_index(self, t=None):
        return self._index_at(self.hourly.get("time", []), self.now() if t is None else t)

    def today_index(self, t=None):
        return self._index_at(self.daily.get("time", []), self.now() if t is None else t)

    def n_days(self):
        return len(self.daily.get("time", []))

    def n_hours(self):
        return len(self.hourly.get("time", []))

    def h(self, key, i, default=None):
        arr = self.hourly.get(key)
        if not arr or i < 0 or i >= len(arr) or arr[i] is None:
            return default
        return arr[i]

    def d(self, key, i, default=None):
        arr = self.daily.get(key)
        if not arr or i < 0 or i >= len(arr) or arr[i] is None:
            return default
        return arr[i]

    def c(self, key, default=None):
        v = self.current.get(key)
        return default if v is None else v

    def day_hour_range(self, day_i):
        """Hourly indices [start, end) belonging to daily entry `day_i`."""
        start_t = self.d("time", day_i)
        if start_t is None:
            return 0, 0
        end_t = self.d("time", day_i + 1, start_t + 86400)
        times = self.hourly.get("time", [])
        idx = [i for i, t in enumerate(times) if start_t <= t < end_t]
        if not idx:
            return 0, 0
        return idx[0], idx[-1] + 1

    @property
    def is_day(self):
        return bool(self.c("is_day", 1))

    def air_value(self, key):
        if not self.air:
            return None
        return (self.air.get("current") or {}).get(key)
