"""Tests for the non-GUI modules. Run: /usr/bin/python3 -m unittest discover tests"""

import time
import unittest

from wxgtk import astro, codes, text
from wxgtk.api import Location
from wxgtk.model import Weather
from wxgtk.units import Units

H = 3600


def make_weather(now=None, codes_seq=None, gusts=10.0):
    """Synthetic Open-Meteo response: yesterday + 3 days, hourly, UTC."""
    now = now or time.time()
    day0 = int(now // 86400) * 86400 - 86400
    n_hours = 24 * 4
    hours = [day0 + i * H for i in range(n_hours)]
    codes_seq = codes_seq or [0] * n_hours
    hourly = {
        "time": hours,
        "temperature_2m": [10 + (i % 24) / 2 for i in range(n_hours)],
        "apparent_temperature": [9 + (i % 24) / 2 for i in range(n_hours)],
        "weather_code": codes_seq,
        "wind_gusts_10m": [gusts] * n_hours,
        "uv_index": [max(0, 6 - abs(12 - i % 24)) for i in range(n_hours)],
        "precipitation": [0.0] * n_hours,
        "precipitation_probability": [0] * n_hours,
        "pressure_msl": [1010 + i * 0.5 for i in range(n_hours)],
        "is_day": [1 if 6 <= i % 24 < 18 else 0 for i in range(n_hours)],
    }
    daily = {
        "time": [day0 + d * 86400 for d in range(4)],
        "temperature_2m_max": [20, 21, 22, 23],
        "temperature_2m_min": [5, 6, 7, 8],
        "precipitation_sum": [0, 0, 0, 4.0],
        "sunrise": [day0 + d * 86400 + 6 * H for d in range(4)],
        "sunset": [day0 + d * 86400 + 18 * H for d in range(4)],
    }
    raw = {
        "forecast": {
            "timezone": "UTC", "utc_offset_seconds": 0,
            "current": {"temperature_2m": 12.0, "apparent_temperature": 12.5, "weather_code": codes_seq[0],
                        "is_day": 1, "wind_speed_10m": 5, "relative_humidity_2m": 40,
                        "pressure_msl": 1020, "dew_point_2m": 3.0},
            "hourly": hourly, "daily": daily,
            "minutely_15": {"time": [], "precipitation": []},
        },
        "air": None,
        "fetched": now,
    }
    w = Weather(raw)
    w.now = lambda: now
    return w


class CodesTest(unittest.TestCase):
    def test_known_and_unknown(self):
        self.assertEqual(codes.describe(0), "Clear")
        self.assertEqual(codes.kind(95), "storm")
        self.assertEqual(codes.icon(0, is_day=False), "weather-clear-night-symbolic")
        self.assertEqual(codes.describe(1234), "Unknown")
        self.assertEqual(codes.describe(None), "Unknown")


class UnitsTest(unittest.TestCase):
    def test_conversions(self):
        u = Units(temp_unit="F", wind_unit="mph", precip_unit="in", pressure_unit="inHg", distance_unit="mi")
        self.assertEqual(u.temp(0), "32°")
        self.assertEqual(u.temp(100), "212°")
        self.assertEqual(u.wind(16.09344), "10 mph")
        self.assertEqual(u.precip(25.4), "1.00″")
        self.assertEqual(u.pressure(1013.25), "29.92")
        self.assertEqual(u.distance(16093.44), "10 mi")
        m = Units()
        self.assertEqual(m.temp(-0.4), "0°")
        self.assertEqual(m.wind(36), "36 km/h")
        self.assertEqual(m.precip(2.25), "2.2 mm")
        self.assertEqual(m.distance(500), "0.5 km")
        self.assertEqual(m.temp(None), "--")

    def test_roundtrip(self):
        u = Units(temp_unit="F", aqi="us")
        self.assertEqual(Units.from_dict(u.to_dict()), u)
        # unknown keys are ignored
        self.assertEqual(Units.from_dict({"temp_unit": "C", "bogus": 1}).temp_unit, "C")


class AstroTest(unittest.TestCase):
    def test_known_full_moon(self):
        # Full moon: 2024-01-25 17:54 UTC
        info = astro.moon_info(1706205240)
        self.assertEqual(info["phase"], "Full Moon")
        self.assertGreater(info["illumination"], 0.98)

    def test_known_new_moon(self):
        # New moon: 2024-02-09 22:59 UTC
        info = astro.moon_info(1707519540)
        self.assertEqual(info["phase"], "New Moon")
        self.assertLess(info["illumination"], 0.02)


class ModelTest(unittest.TestCase):
    def test_indices(self):
        now = (int(time.time() // 86400) * 86400) + 10 * H + 600
        w = make_weather(now)
        self.assertEqual(w.today_index(), 1)  # index 0 is yesterday (past_days=1)
        self.assertEqual(w.hour_index(), 24 + 10)
        self.assertEqual(w.day_hour_range(1), (24, 48))

    def test_location_id(self):
        self.assertEqual(Location("X", 1.23456, -2.5).id, "1.235,-2.500")


class TextTest(unittest.TestCase):
    def setUp(self):
        self.u = Units(clock="24h")

    def test_summary_change(self):
        now = (int(time.time() // 86400) * 86400) + 10 * H
        seq = [0] * 96
        for i in range(24 + 15, 96):
            seq[i] = 63
        w = make_weather(now, seq, gusts=45)
        s = text.hourly_summary(w, self.u)
        self.assertIn("Rainy conditions expected around 15", s)
        self.assertIn("Wind gusts are up to 45 km/h", s)

    def test_summary_steady(self):
        w = make_weather((int(time.time() // 86400) * 86400) + 10 * H)
        self.assertEqual(text.hourly_summary(w, self.u), "Clear conditions will continue for the rest of the day.")

    def test_next_hour(self):
        w = make_weather()
        self.assertIsNone(text.next_hour_precip(w))
        now = w.now()
        w.m15 = {"time": [now - 300 + i * 900 for i in range(8)], "precipitation": [0, 0, 0.5, 0.5, 0, 0, 0, 0]}
        headline, values, _ = text.next_hour_precip(w)
        self.assertTrue(headline.startswith("Rain starting in"))
        self.assertEqual(len(values), 8)
        w.m15["precipitation"] = [0.5, 0.5, 0, 0, 0, 0, 0, 0]
        self.assertTrue(text.next_hour_precip(w)[0].startswith("Rain stopping in"))

    def test_time_formats(self):
        from datetime import datetime
        dt = datetime(2026, 1, 1, 15, 5)
        self.assertEqual(text.fmt_time(dt, Units(clock="12h")), "3:05 PM")
        self.assertEqual(text.fmt_time(dt, Units(clock="24h")), "15:05")
        self.assertEqual(text.fmt_hour(dt.replace(hour=0), Units(clock="12h")), "12 AM")

    def test_levels(self):
        self.assertEqual(text.uv_level(0), "Low")
        self.assertEqual(text.uv_level(7), "High")
        self.assertEqual(text.uv_level(12), "Extreme")
        self.assertEqual(text.aqi_category(42, "us")[0], "Good")
        self.assertEqual(text.aqi_category(42, "eu")[0], "Moderate")
        self.assertEqual(text.wind_direction_name(350), "N")
        self.assertEqual(text.wind_direction_name(225), "SW")
        self.assertEqual(text.visibility_text(30000), "Perfectly clear view.")

    def test_pressure_trend(self):
        w = make_weather()
        w.current["pressure_msl"] = w.h("pressure_msl", w.hour_index() - 3) + 5
        self.assertEqual(text.pressure_trend(w), 1)

    def test_precip_texts(self):
        w = make_weather((int(time.time() // 86400) * 86400) + 10 * H)
        past, nxt = text.precipitation_texts(w, self.u)
        self.assertEqual(past, 0)
        self.assertIn("4.0 mm", nxt)


if __name__ == "__main__":
    unittest.main()
