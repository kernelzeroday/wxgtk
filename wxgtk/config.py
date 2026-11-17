"""Persistent settings and a small on-disk cache of the last forecast per location."""

import json
import os
from pathlib import Path

from .api import Location
from .units import Units


def _xdg(var, fallback):
    return Path(os.environ.get(var) or Path.home() / fallback) / "wxgtk"


CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config")
CACHE_DIR = _xdg("XDG_CACHE_HOME", ".cache")
CONFIG_FILE = CONFIG_DIR / "config.json"


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


class Config:
    def __init__(self):
        self.locations: list[Location] = []
        self.units = Units.default_for_locale()
        self.selected = 0
        self.use_current_location = False
        self.load()

    def load(self):
        try:
            data = json.loads(CONFIG_FILE.read_text())
        except (OSError, ValueError):
            return
        self.units = Units.from_dict(data.get("units"))
        self.locations = []
        for d in data.get("locations", []):
            try:
                self.locations.append(Location.from_dict(d))
            except (KeyError, TypeError, ValueError):
                continue
        self.selected = int(data.get("selected", 0) or 0)
        self.use_current_location = bool(data.get("use_current_location", False))

    def save(self):
        _atomic_write(CONFIG_FILE, {
            "locations": [l.to_dict() for l in self.locations],
            "units": self.units.to_dict(),
            "selected": self.selected,
            "use_current_location": self.use_current_location,
        })


def cache_path(loc_id):
    return CACHE_DIR / f"{loc_id.replace(',', '_')}.json"


def save_cache(loc_id, raw):
    try:
        _atomic_write(cache_path(loc_id), raw)
    except OSError:
        pass


def load_cache(loc_id):
    try:
        return json.loads(cache_path(loc_id).read_text())
    except (OSError, ValueError):
        return None
