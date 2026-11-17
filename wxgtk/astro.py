"""Moon phase calculations (simple synodic-month model, accurate to ~1 day)."""

import math

SYNODIC = 29.530588853
_KNOWN_NEW_MOON_JD = 2451550.1  # 2000-01-06 18:14 UTC

PHASES = [
    (1.0, "New Moon"),
    (6.4, "Waxing Crescent"),
    (8.4, "First Quarter"),
    (13.8, "Waxing Gibbous"),
    (15.8, "Full Moon"),
    (21.1, "Waning Gibbous"),
    (23.1, "Last Quarter"),
    (28.5, "Waning Crescent"),
    (SYNODIC + 1, "New Moon"),
]


def julian_day(unix_ts):
    return unix_ts / 86400.0 + 2440587.5


def moon_age(unix_ts):
    """Days since the last new moon (0 .. SYNODIC)."""
    return (julian_day(unix_ts) - _KNOWN_NEW_MOON_JD) % SYNODIC


def illumination(age):
    return (1 - math.cos(2 * math.pi * age / SYNODIC)) / 2


def phase_name(age):
    for limit, name in PHASES:
        if age < limit:
            return name
    return "New Moon"


def days_until_full(age):
    d = (SYNODIC / 2 - age) % SYNODIC
    return d


def days_until_new(age):
    return (SYNODIC - age) % SYNODIC


def moon_info(unix_ts):
    age = moon_age(unix_ts)
    return {
        "age": age,
        "illumination": illumination(age),
        "phase": phase_name(age),
        "next_full": days_until_full(age),
        "next_new": days_until_new(age),
    }
