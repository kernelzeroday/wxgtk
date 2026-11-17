"""Unit preferences and value formatting. All raw data is metric."""

from dataclasses import asdict, dataclass, fields
import locale

TEMP_UNITS = [("C", "Celsius (°C)"), ("F", "Fahrenheit (°F)")]
WIND_UNITS = [("kmh", "km/h"), ("ms", "m/s"), ("mph", "mph"), ("kn", "Knots")]
PRECIP_UNITS = [("mm", "Millimeters"), ("in", "Inches")]
PRESSURE_UNITS = [("hPa", "hPa"), ("inHg", "inHg"), ("mmHg", "mmHg")]
DISTANCE_UNITS = [("km", "Kilometers"), ("mi", "Miles")]
AQI_SCALES = [("us", "US AQI"), ("eu", "European AQI")]
CLOCK_FORMATS = [("auto", "System"), ("12h", "12-hour"), ("24h", "24-hour")]

_IMPERIAL_LOCALES = ("en_US", "en_LR", "my_MM")


@dataclass
class Units:
    temp_unit: str = "C"
    wind_unit: str = "kmh"
    precip_unit: str = "mm"
    pressure_unit: str = "hPa"
    distance_unit: str = "km"
    aqi: str = "eu"
    clock: str = "auto"

    @classmethod
    def default_for_locale(cls):
        try:
            loc = locale.getlocale(locale.LC_MEASUREMENT)[0] or locale.getlocale()[0] or ""
        except (AttributeError, ValueError):
            loc = ""
        if loc.startswith(_IMPERIAL_LOCALES):
            return cls(temp_unit="F", wind_unit="mph", precip_unit="in", pressure_unit="inHg",
                       distance_unit="mi", aqi="us")
        return cls()

    @classmethod
    def from_dict(cls, d):
        base = cls.default_for_locale()
        names = {f.name for f in fields(cls)}
        for k, v in (d or {}).items():
            if k in names and isinstance(v, str):
                setattr(base, k, v)
        return base

    def to_dict(self):
        return asdict(self)

    # ---- temperature -------------------------------------------------
    def temp_value(self, c):
        return c if self.temp_unit == "C" else c * 9 / 5 + 32

    def temp(self, c):
        if c is None:
            return "--"
        return f"{round(self.temp_value(c))}°"

    def temp_delta(self, dc):
        """A temperature difference (no offset)."""
        return dc if self.temp_unit == "C" else dc * 9 / 5

    # ---- wind ----------------------------------------------------------
    def wind_value(self, kmh):
        return {
            "kmh": kmh,
            "ms": kmh / 3.6,
            "mph": kmh / 1.609344,
            "kn": kmh / 1.852,
        }.get(self.wind_unit, kmh)

    def wind_label(self):
        return {"kmh": "km/h", "ms": "m/s", "mph": "mph", "kn": "kn"}.get(self.wind_unit, "km/h")

    def wind(self, kmh):
        if kmh is None:
            return "--"
        return f"{round(self.wind_value(kmh))} {self.wind_label()}"

    # ---- precipitation -------------------------------------------------
    def precip(self, mm):
        if mm is None:
            return "--"
        if self.precip_unit == "in":
            inches = mm / 25.4
            return f"{inches:.2f}″" if inches < 10 else f"{inches:.1f}″"
        return f"{mm:.1f} mm" if mm < 10 else f"{round(mm)} mm"

    # ---- pressure ------------------------------------------------------
    def pressure_value(self, hpa):
        return {"hPa": hpa, "inHg": hpa * 0.0295300, "mmHg": hpa * 0.750062}.get(self.pressure_unit, hpa)

    def pressure(self, hpa):
        if hpa is None:
            return "--"
        v = self.pressure_value(hpa)
        if self.pressure_unit == "inHg":
            return f"{v:.2f}"
        return f"{round(v)}"

    # ---- distance ------------------------------------------------------
    def distance(self, meters):
        if meters is None:
            return "--"
        km = meters / 1000
        if self.distance_unit == "mi":
            mi = km / 1.609344
            return f"{mi:.1f} mi" if mi < 10 else f"{round(mi)} mi"
        return f"{km:.1f} km" if km < 10 else f"{round(km)} km"
