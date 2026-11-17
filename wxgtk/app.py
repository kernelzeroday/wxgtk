import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from . import APP_ID, VERSION  # noqa: E402
from .config import Config  # noqa: E402


class WeatherApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.config = None
        for name, cb, accels in (
            ("quit", lambda *_: self.quit(), ["<Ctrl>q"]),
            ("preferences", lambda *_: self._window().show_preferences(), ["<Ctrl>comma"]),
            ("about", lambda *_: self._about(), []),
        ):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            self.add_action(act)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)
        self.set_accels_for_action("window.close", ["<Ctrl>w"])

    def do_startup(self):
        Adw.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_path(str(Path(__file__).with_name("style.css")))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        win = self.get_active_window()
        if win is None:
            from .window import WeatherWindow
            self.config = Config()
            win = WeatherWindow(self, self.config)
        win.present()

    def _window(self):
        return self.get_active_window()

    def _about(self):
        about = Adw.AboutDialog(
            application_name="Weather",
            application_icon="weather-few-clouds-symbolic",
            version=VERSION,
            developer_name="wxgtk contributors",
            comments="A GTK4 weather app.\n\nForecast and air quality data by Open-Meteo.com (CC BY 4.0). "
                     "Place names for your current location by OpenStreetMap Nominatim.",
            website="https://github.com/kernelzeroday/wxgtk",
        )
        about.present(self._window())


def main():
    return WeatherApp().run(sys.argv)
