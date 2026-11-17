"""Best-effort current location via GeoClue."""

from gi.repository import GLib

from . import APP_ID

try:
    import gi
    gi.require_version("Geoclue", "2.0")
    from gi.repository import Geoclue
except (ImportError, ValueError):  # pragma: no cover
    Geoclue = None

_pending = []  # keep the Simple objects alive


def locate(callback, timeout=20):
    """callback(lat, lon, error): exactly one of (lat, lon) / error is set."""
    if Geoclue is None:
        callback(None, None, "GeoClue is not available on this system")
        return
    state = {"done": False}

    def finish(lat, lon, err):
        if not state["done"]:
            state["done"] = True
            callback(lat, lon, err)

    def on_ready(_src, res):
        try:
            simple = Geoclue.Simple.new_finish(res)
            _pending.append(simple)
            loc = simple.get_location()
            finish(loc.props.latitude, loc.props.longitude, None)
        except GLib.Error as e:
            finish(None, None, e.message)

    def on_timeout():
        finish(None, None, "Timed out waiting for location")
        return GLib.SOURCE_REMOVE

    Geoclue.Simple.new(APP_ID, Geoclue.AccuracyLevel.CITY, None, on_ready)
    GLib.timeout_add_seconds(timeout, on_timeout)
