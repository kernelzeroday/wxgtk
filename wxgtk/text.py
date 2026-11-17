"""Human-readable summaries, in the spirit of Apple Weather's descriptive text."""

from . import codes

# ---- time formatting --------------------------------------------------------

_system_24h = None


def system_uses_24h():
    global _system_24h
    if _system_24h is None:
        _system_24h = False
        try:
            from gi.repository import Gio
            src = Gio.SettingsSchemaSource.get_default()
            if src and src.lookup("org.gnome.desktop.interface", True):
                _system_24h = Gio.Settings.new("org.gnome.desktop.interface").get_string("clock-format") == "24h"
        except Exception:
            pass
    return _system_24h


def is_24h(units):
    if units.clock == "24h":
        return True
    if units.clock == "12h":
        return False
    return system_uses_24h()


def fmt_hour(dt, units):
    if is_24h(units):
        return f"{dt.hour:02d}"
    h = dt.hour % 12 or 12
    return f"{h} {'AM' if dt.hour < 12 else 'PM'}"


def fmt_time(dt, units):
    if is_24h(units):
        return f"{dt.hour:02d}:{dt.minute:02d}"
    h = dt.hour % 12 or 12
    return f"{h}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def fmt_duration(seconds):
    seconds = int(seconds)
    h, m = divmod(seconds // 60, 60)
    return f"{h} hr {m} min" if h else f"{m} min"


# ---- hourly forecast summary ------------------------------------------------

def hourly_summary(w, units, hours=24):
    """E.g. 'Rainy conditions expected around 3 PM. Wind gusts are up to 40 km/h.'"""
    i0 = w.hour_index()
    cur_kind = codes.kind(w.c("weather_code", w.h("weather_code", i0)))
    end = min(w.n_hours(), i0 + hours)
    sentence = None
    for i in range(i0 + 1, end):
        k = codes.kind(w.h("weather_code", i))
        if k != cur_kind:
            when = fmt_hour(w.local(w.h("time", i)), units)
            sentence = f"{codes.KIND_ADJECTIVE[k]} conditions expected around {when}."
            break
    if sentence is None:
        rest = "the rest of the day" if hours <= 24 else "the next while"
        sentence = f"{codes.KIND_ADJECTIVE[cur_kind]} conditions will continue for {rest}."
    gusts = [w.h("wind_gusts_10m", i, 0) for i in range(i0, end)]
    max_gust = max(gusts, default=0)
    if max_gust >= 30:
        sentence += f" Wind gusts are up to {units.wind(max_gust)}."
    return sentence


# ---- next-hour precipitation ------------------------------------------------

def next_hour_precip(w, threshold=0.1, horizon=8):
    """Look at the 15-minute precipitation data for the next 2 hours.

    Returns None when nothing is expected, else (headline, values, start_ts).
    """
    times = w.m15.get("time") or []
    vals = w.m15.get("precipitation") or []
    if not times or not vals:
        return None
    now = w.now()
    start = 0
    for i, t in enumerate(times):
        if t <= now:
            start = i
    window = [(times[i], vals[i] or 0.0) for i in range(start, min(len(times), start + horizon))]
    if not window or all(v < threshold for _, v in window):
        return None
    code = w.c("weather_code", 0)
    noun = "Snow" if codes.kind(code) == "snow" else "Rain"
    raining_now = window[0][1] >= threshold
    if raining_now:
        stop = next((t for t, v in window if v < threshold), None)
        if stop is None:
            headline = f"{noun} for the next two hours"
        else:
            headline = f"{noun} stopping in ~{max(15, round((stop - now) / 60 / 5) * 5)} min"
    else:
        begin = next(t for t, v in window if v >= threshold)
        headline = f"{noun} starting in ~{max(5, round((begin - now) / 60 / 5) * 5)} min"
    return headline, [v for _, v in window], window[0][0]


# ---- tiles ------------------------------------------------------------------

def uv_level(uv):
    if uv is None:
        return "--"
    if uv < 3:
        return "Low"
    if uv < 6:
        return "Moderate"
    if uv < 8:
        return "High"
    if uv < 11:
        return "Very High"
    return "Extreme"


def uv_advice(w, units):
    d = w.today_index()
    s, e = w.day_hour_range(d)
    high = [i for i in range(s, e) if w.h("uv_index", i, 0) >= 3]
    if not high:
        if w.c("uv_index", 0) < 3:
            return "Low for the rest of the day."
        return "Use sun protection now."
    a = fmt_hour(w.local(w.h("time", high[0])), units)
    b = fmt_hour(w.local(w.h("time", high[-1]) + 3600), units)
    if w.now() > w.h("time", high[-1]) + 3600:
        return "Low for the rest of the day."
    return f"Use sun protection {a}–{b}."


def feels_like_text(w):
    t = w.c("temperature_2m")
    a = w.c("apparent_temperature")
    if t is None or a is None:
        return ""
    diff = a - t
    if abs(diff) < 2:
        return "Similar to the actual temperature."
    if diff < 0:
        if w.c("wind_speed_10m", 0) >= 12:
            return "Wind is making it feel colder."
        return "Feels colder than the actual temperature."
    if w.c("relative_humidity_2m", 0) >= 55:
        return "Humidity is making it feel warmer."
    return "Feels warmer than the actual temperature."


def humidity_text(w, units):
    dp = w.c("dew_point_2m")
    if dp is None:
        return ""
    return f"The dew point is {units.temp(dp)} right now."


def visibility_text(meters):
    if meters is None:
        return ""
    km = meters / 1000
    if km >= 20:
        return "Perfectly clear view."
    if km >= 10:
        return "Clear view."
    if km >= 5:
        return "Light haze is affecting visibility."
    if km >= 1:
        return "Haze is affecting visibility."
    return "Fog is severely limiting visibility."


def pressure_trend(w):
    """Compare current pressure to 3 hours ago: returns -1, 0 or 1."""
    i = w.hour_index()
    now_p = w.c("pressure_msl", w.h("pressure_msl", i))
    past = w.h("pressure_msl", i - 3)
    if now_p is None or past is None:
        return 0
    delta = now_p - past
    if delta > 1:
        return 1
    if delta < -1:
        return -1
    return 0


def pressure_text(trend):
    return {1: "Rising.", -1: "Falling.", 0: "Steady."}[trend]


def precipitation_texts(w, units):
    """(last 24h total, next expected sentence)."""
    i = w.hour_index()
    past = sum(w.h("precipitation", j, 0) for j in range(max(0, i - 23), i + 1))
    d0 = w.today_index()
    nxt = "None expected in the next 10 days."
    for d in range(d0, w.n_days()):
        amt = w.d("precipitation_sum", d, 0)
        if amt >= 0.5:
            if d == d0:
                remaining = sum(w.h("precipitation", j, 0) for j in range(i + 1, w.day_hour_range(d)[1]))
                if remaining >= 0.2:
                    nxt = f"{units.precip(remaining)} expected in the rest of today."
                    break
                continue
            day = "tomorrow" if d == d0 + 1 else w.local(w.d("time", d)).strftime("%A")
            nxt = f"Next expected is {units.precip(amt)} {'' if day == 'tomorrow' else 'on '}{day}.".replace("  ", " ")
            break
    return past, nxt


US_AQI = [
    (50, "Good", "Air quality is satisfactory and poses little or no risk."),
    (100, "Moderate", "Acceptable; some pollutants may be a concern for very sensitive people."),
    (150, "Unhealthy for Sensitive Groups", "Sensitive groups may experience health effects."),
    (200, "Unhealthy", "Everyone may begin to experience health effects."),
    (300, "Very Unhealthy", "Health alert: everyone may experience serious effects."),
    (10_000, "Hazardous", "Health warning of emergency conditions."),
]
EU_AQI = [
    (20, "Good", "The air quality is good. Enjoy your usual outdoor activities."),
    (40, "Fair", "Enjoy your usual outdoor activities."),
    (60, "Moderate", "Consider reducing intense outdoor activities if you have symptoms."),
    (80, "Poor", "Consider reducing intense activities outdoors."),
    (100, "Very Poor", "Reduce physical activities outdoors."),
    (10_000, "Extremely Poor", "Avoid physical activities outdoors."),
]


def aqi_category(value, scale="us"):
    table = US_AQI if scale == "us" else EU_AQI
    if value is None:
        return "Unavailable", ""
    for limit, label, desc in table:
        if value <= limit:
            return label, desc
    return table[-1][1], table[-1][2]


def wind_direction_name(deg):
    if deg is None:
        return ""
    names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
             "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names[int((deg % 360) / 22.5 + 0.5) % 16]


def beaufort(kmh):
    scale = [1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118]
    names = ["Calm", "Light air", "Light breeze", "Gentle breeze", "Moderate breeze",
             "Fresh breeze", "Strong breeze", "Near gale", "Gale", "Strong gale",
             "Storm", "Violent storm", "Hurricane force"]
    for i, lim in enumerate(scale):
        if kmh < lim:
            return i, names[i]
    return 12, names[12]
