"""WMO weather interpretation codes (as used by Open-Meteo)."""

CLEAR = "weather-clear-symbolic"
CLEAR_N = "weather-clear-night-symbolic"
FEW = "weather-few-clouds-symbolic"
FEW_N = "weather-few-clouds-night-symbolic"
OVERCAST = "weather-overcast-symbolic"
FOG = "weather-fog-symbolic"
SCATTERED = "weather-showers-scattered-symbolic"
SHOWERS = "weather-showers-symbolic"
SNOW = "weather-snow-symbolic"
STORM = "weather-storm-symbolic"

# code: (description, day icon, night icon, kind)
WMO = {
    0: ("Clear", CLEAR, CLEAR_N, "clear"),
    1: ("Mostly Clear", FEW, FEW_N, "clear"),
    2: ("Partly Cloudy", FEW, FEW_N, "partly"),
    3: ("Cloudy", OVERCAST, OVERCAST, "cloudy"),
    45: ("Fog", FOG, FOG, "fog"),
    48: ("Freezing Fog", FOG, FOG, "fog"),
    51: ("Light Drizzle", SCATTERED, SCATTERED, "rain"),
    53: ("Drizzle", SCATTERED, SCATTERED, "rain"),
    55: ("Heavy Drizzle", SHOWERS, SHOWERS, "rain"),
    56: ("Freezing Drizzle", SCATTERED, SCATTERED, "rain"),
    57: ("Freezing Drizzle", SHOWERS, SHOWERS, "rain"),
    61: ("Light Rain", SCATTERED, SCATTERED, "rain"),
    63: ("Rain", SHOWERS, SHOWERS, "rain"),
    65: ("Heavy Rain", SHOWERS, SHOWERS, "rain"),
    66: ("Freezing Rain", SHOWERS, SHOWERS, "rain"),
    67: ("Heavy Freezing Rain", SHOWERS, SHOWERS, "rain"),
    71: ("Light Snow", SNOW, SNOW, "snow"),
    73: ("Snow", SNOW, SNOW, "snow"),
    75: ("Heavy Snow", SNOW, SNOW, "snow"),
    77: ("Snow Grains", SNOW, SNOW, "snow"),
    80: ("Light Showers", SCATTERED, SCATTERED, "rain"),
    81: ("Showers", SHOWERS, SHOWERS, "rain"),
    82: ("Heavy Showers", SHOWERS, SHOWERS, "rain"),
    85: ("Snow Showers", SNOW, SNOW, "snow"),
    86: ("Heavy Snow Showers", SNOW, SNOW, "snow"),
    95: ("Thunderstorms", STORM, STORM, "storm"),
    96: ("Thunderstorms with Hail", STORM, STORM, "storm"),
    99: ("Severe Thunderstorms", STORM, STORM, "storm"),
}

_UNKNOWN = ("Unknown", OVERCAST, OVERCAST, "cloudy")

KIND_ADJECTIVE = {
    "clear": "Clear",
    "partly": "Partly cloudy",
    "cloudy": "Cloudy",
    "fog": "Foggy",
    "rain": "Rainy",
    "snow": "Snowy",
    "storm": "Stormy",
}


def lookup(code):
    try:
        return WMO.get(int(code), _UNKNOWN)
    except (TypeError, ValueError):
        return _UNKNOWN


def describe(code):
    return lookup(code)[0]


def icon(code, is_day=True):
    entry = lookup(code)
    return entry[1] if is_day else entry[2]


def kind(code):
    return lookup(code)[3]


# Precipitation intensity for the sky animation: 0 light, 1 moderate, 2 heavy.
_INTENSITY = {
    51: 0, 53: 1, 55: 2, 56: 0, 57: 1,
    61: 0, 63: 1, 65: 2, 66: 0, 67: 2,
    71: 0, 73: 1, 75: 2, 77: 0,
    80: 0, 81: 1, 82: 2, 85: 0, 86: 2,
    95: 1, 96: 1, 99: 2,
}
_FREEZING = {56, 57, 66, 67}
_HAIL = {96, 99}


def intensity(code):
    try:
        return _INTENSITY.get(int(code), 1)
    except (TypeError, ValueError):
        return 1


def variant(code):
    """'freezing', 'hail' or None — extra detail the sky animation shows."""
    try:
        code = int(code)
    except (TypeError, ValueError):
        return None
    if code in _FREEZING:
        return "freezing"
    if code in _HAIL:
        return "hail"
    return None
