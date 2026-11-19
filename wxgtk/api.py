"""Open-Meteo client (forecast, air quality, geocoding) — no API key needed."""

from dataclasses import asdict, dataclass
import json
import logging
import time
import urllib.parse
import urllib.request

from . import VERSION

log = logging.getLogger(__name__)

USER_AGENT = f"wxgtk/{VERSION} (GTK4 weather app)"

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

CURRENT_VARS = [
    "temperature_2m", "relative_humidity_2m", "apparent_temperature", "is_day",
    "precipitation", "weather_code", "cloud_cover", "pressure_msl",
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m", "visibility",
    "uv_index", "dew_point_2m",
]
HOURLY_VARS = [
    "temperature_2m", "relative_humidity_2m", "dew_point_2m", "apparent_temperature",
    "precipitation_probability", "precipitation", "weather_code", "pressure_msl",
    "visibility", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
    "uv_index", "is_day", "cloud_cover",
]
DAILY_VARS = [
    "weather_code", "temperature_2m_max", "temperature_2m_min",
    "apparent_temperature_max", "apparent_temperature_min", "sunrise", "sunset",
    "daylight_duration", "uv_index_max", "precipitation_sum",
    "precipitation_probability_max", "wind_speed_10m_max", "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
]
AIR_CURRENT = ["us_aqi", "european_aqi", "pm2_5", "pm10", "ozone", "nitrogen_dioxide",
               "sulphur_dioxide", "carbon_monoxide"]

FORECAST_DAYS = 10


class ApiError(Exception):
    pass


@dataclass
class Location:
    name: str
    lat: float
    lon: float
    region: str = ""
    country: str = ""
    timezone: str = ""
    is_current: bool = False

    @property
    def id(self):
        return f"{self.lat:.3f},{self.lon:.3f}"

    @property
    def subtitle(self):
        return ", ".join(p for p in (self.region, self.country) if p)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d.get("name", "Unknown"),
            lat=float(d["lat"]),
            lon=float(d["lon"]),
            region=d.get("region", ""),
            country=d.get("country", ""),
            timezone=d.get("timezone", ""),
            is_current=bool(d.get("is_current", False)),
        )


def _get_json(url, params, timeout=20):
    full = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            reason = json.load(e).get("reason", str(e))
        except Exception:
            reason = str(e)
        log.warning("GET %s -> HTTP %s: %s", url, e.code, reason)
        raise ApiError(reason) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        log.warning("GET %s -> network error: %r", url, getattr(e, "reason", e))
        raise ApiError(f"Network error: {getattr(e, 'reason', e)}") from e
    except ValueError as e:
        log.warning("GET %s -> invalid JSON: %s", url, e)
        raise ApiError(f"Invalid response: {e}") from e
    if isinstance(data, dict) and data.get("error"):
        log.warning("GET %s -> API error: %s", url, data.get("reason"))
        raise ApiError(data.get("reason", "Unknown API error"))
    return data


def fetch_forecast(lat, lon):
    return _get_json(FORECAST_URL, {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "current": ",".join(CURRENT_VARS),
        "hourly": ",".join(HOURLY_VARS),
        "daily": ",".join(DAILY_VARS),
        "minutely_15": "precipitation",
        "past_days": 1,
        "forecast_days": FORECAST_DAYS,
        "timezone": "auto",
        "timeformat": "unixtime",
    })


def fetch_air_quality(lat, lon):
    return _get_json(AIR_URL, {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "current": ",".join(AIR_CURRENT),
        "hourly": "us_aqi,european_aqi",
        "forecast_days": 5,
        "timezone": "auto",
        "timeformat": "unixtime",
    })


def fetch_weather(lat, lon):
    """Fetch everything needed for one location. Air quality is optional."""
    forecast = fetch_forecast(lat, lon)
    try:
        air = fetch_air_quality(lat, lon)
    except ApiError as e:
        log.warning("Air quality unavailable for %.4f,%.4f: %s", lat, lon, e)
        air = None
    return {"forecast": forecast, "air": air, "fetched": time.time()}


def search_locations(query, count=10):
    query = query.strip()
    if len(query) < 2:
        return []
    data = _get_json(GEOCODE_URL, {"name": query, "count": count, "language": "en", "format": "json"})
    out = []
    for r in data.get("results") or []:
        out.append(Location(
            name=r.get("name", "?"),
            lat=float(r["latitude"]),
            lon=float(r["longitude"]),
            region=r.get("admin1", "") or "",
            country=r.get("country", "") or "",
            timezone=r.get("timezone", "") or "",
        ))
    return out


def reverse_geocode(lat, lon):
    """Best-effort place name for coordinates (OpenStreetMap Nominatim)."""
    try:
        data = _get_json(REVERSE_URL, {
            "lat": f"{lat:.4f}", "lon": f"{lon:.4f}", "format": "jsonv2", "zoom": 10,
            "accept-language": "en",
        }, timeout=10)
    except ApiError as e:
        log.warning("Reverse geocoding failed for %.4f,%.4f: %s", lat, lon, e)
        return Location("My Location", lat, lon, is_current=True)
    addr = data.get("address", {})
    name = (addr.get("city") or addr.get("town") or addr.get("village")
            or addr.get("municipality") or addr.get("county") or data.get("name") or "My Location")
    return Location(name, lat, lon, region=addr.get("state", ""), country=addr.get("country", ""),
                    is_current=True)
