from gi.repository import Adw, Gtk

from . import units as U


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, config, on_changed):
        super().__init__(title="Preferences")
        self.config = config
        self.on_changed = on_changed
        page = Adw.PreferencesPage(title="Units", icon_name="preferences-system-symbolic")
        group = Adw.PreferencesGroup(title="Units")
        page.add(group)
        for attr, title, options in (
            ("temp_unit", "Temperature", U.TEMP_UNITS),
            ("wind_unit", "Wind Speed", U.WIND_UNITS),
            ("precip_unit", "Precipitation", U.PRECIP_UNITS),
            ("pressure_unit", "Pressure", U.PRESSURE_UNITS),
            ("distance_unit", "Distance", U.DISTANCE_UNITS),
        ):
            group.add(self._combo(attr, title, options))
        other = Adw.PreferencesGroup(title="Display")
        other.add(self._combo("aqi", "Air Quality Index", U.AQI_SCALES))
        other.add(self._combo("clock", "Time Format", U.CLOCK_FORMATS))
        page.add(other)
        self.add(page)

    def _combo(self, attr, title, options):
        row = Adw.ComboRow(title=title, model=Gtk.StringList.new([o[1] for o in options]))
        keys = [o[0] for o in options]
        cur = getattr(self.config.units, attr)
        row.set_selected(keys.index(cur) if cur in keys else 0)

        def changed(r, _p):
            setattr(self.config.units, attr, keys[r.get_selected()])
            self.config.save()
            self.on_changed()

        row.connect("notify::selected", changed)
        return row
