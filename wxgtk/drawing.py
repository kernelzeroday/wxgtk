"""Custom Cairo-drawn widgets: animated sky, charts, gauges and dials."""

import math
import random

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Pango, PangoCairo  # noqa: E402
import cairo  # noqa: E402

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

TEMP_STOPS = [
    (-25, (0.62, 0.45, 0.98)),
    (-5, (0.38, 0.62, 1.00)),
    (5, (0.35, 0.82, 0.95)),
    (14, (0.45, 0.88, 0.55)),
    (21, (0.98, 0.85, 0.30)),
    (28, (1.00, 0.58, 0.20)),
    (36, (1.00, 0.30, 0.25)),
]

UV_STOPS = [(0, (0.30, 0.80, 0.30)), (3, (0.95, 0.85, 0.20)), (6, (1.0, 0.55, 0.15)),
            (8, (0.95, 0.25, 0.25)), (11, (0.65, 0.30, 0.85))]
US_AQI_STOPS = [(0, (0.30, 0.80, 0.30)), (50, (0.95, 0.85, 0.20)), (100, (1.0, 0.55, 0.15)),
                (150, (0.95, 0.25, 0.25)), (200, (0.65, 0.30, 0.85)), (300, (0.55, 0.15, 0.25))]
EU_AQI_STOPS = [(0, (0.30, 0.80, 0.75)), (20, (0.35, 0.80, 0.35)), (40, (0.95, 0.85, 0.20)),
                (60, (1.0, 0.55, 0.15)), (80, (0.95, 0.25, 0.25)), (100, (0.55, 0.15, 0.40))]


def lerp(a, b, t):
    return a + (b - a) * t


def color_at(stops, v):
    if v <= stops[0][0]:
        return stops[0][1]
    for (v0, c0), (v1, c1) in zip(stops, stops[1:]):
        if v <= v1:
            t = (v - v0) / (v1 - v0)
            return tuple(lerp(a, b, t) for a, b in zip(c0, c1))
    return stops[-1][1]


def temp_color(celsius):
    return color_at(TEMP_STOPS, celsius)


def rounded_rect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def fg(widget):
    c = widget.get_color()
    return c.red, c.green, c.blue


def text(widget, cr, s, x, y, size=9.0, align="left", valign="top", bold=False, alpha=1.0, color=None):
    layout = widget.create_pango_layout(s)
    desc = widget.get_pango_context().get_font_description().copy()
    desc.set_size(int(size * Pango.SCALE))
    desc.set_weight(Pango.Weight.BOLD if bold else Pango.Weight.NORMAL)
    layout.set_font_description(desc)
    _, logical = layout.get_pixel_extents()
    tw, th = logical.width, logical.height
    if align == "center":
        x -= tw / 2
    elif align == "right":
        x -= tw
    if valign == "middle":
        y -= th / 2
    elif valign == "bottom":
        y -= th
    r, g, b = color or fg(widget)
    cr.set_source_rgba(r, g, b, alpha)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    return tw, th


def gradient_from_stops(x0, x1, stops, vmin, vmax):
    grad = cairo.LinearGradient(x0, 0, x1, 0)
    span = (vmax - vmin) or 1
    for v, (r, g, b) in stops:
        grad.add_color_stop_rgb(min(1, max(0, (v - vmin) / span)), r, g, b)
    return grad


def nice_ticks(lo, hi, target=4):
    if hi - lo < 1e-9:
        hi = lo + 1
    raw = (hi - lo) / target
    mag = 10 ** math.floor(math.log10(raw))
    step = mag * 10
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    start = math.floor(lo / step) * step
    end = math.ceil(hi / step) * step
    ticks = []
    v = start
    while v <= end + step * 1e-6:
        ticks.append(round(v, 10))
        v += step
    return ticks


class _Area(Gtk.DrawingArea):
    def __init__(self, width=-1, height=-1):
        super().__init__()
        if width > 0:
            self.set_content_width(width)
        if height > 0:
            self.set_content_height(height)
        self.set_draw_func(self._draw)

    def _draw(self, area, cr, w, h):
        self.draw(cr, w, h)

    def draw(self, cr, w, h):  # pragma: no cover - overridden
        pass


# ---------------------------------------------------------------------------
# animated sky
# ---------------------------------------------------------------------------

SKY = {
    ("clear", True): ((0.16, 0.47, 0.86), (0.48, 0.73, 0.95)),
    ("clear", False): ((0.03, 0.06, 0.16), (0.14, 0.21, 0.40)),
    ("partly", True): ((0.27, 0.50, 0.78), (0.58, 0.72, 0.86)),
    ("partly", False): ((0.07, 0.10, 0.20), (0.20, 0.25, 0.38)),
    ("cloudy", True): ((0.38, 0.45, 0.54), (0.58, 0.64, 0.71)),
    ("cloudy", False): ((0.10, 0.12, 0.17), (0.23, 0.27, 0.33)),
    ("fog", True): ((0.45, 0.49, 0.52), (0.62, 0.65, 0.67)),
    ("fog", False): ((0.14, 0.15, 0.18), (0.29, 0.31, 0.34)),
    ("rain", True): ((0.27, 0.34, 0.43), (0.45, 0.52, 0.60)),
    ("rain", False): ((0.07, 0.09, 0.13), (0.17, 0.21, 0.27)),
    ("snow", True): ((0.42, 0.50, 0.62), (0.65, 0.71, 0.79)),
    ("snow", False): ((0.13, 0.16, 0.22), (0.27, 0.32, 0.40)),
    ("storm", True): ((0.16, 0.18, 0.24), (0.33, 0.36, 0.43)),
    ("storm", False): ((0.05, 0.05, 0.09), (0.16, 0.17, 0.23)),
}


def sky_wind(speed_kmh, direction_deg):
    """Horizontal wind for the sky animation, -1 (blowing left) .. 1 (blowing right).

    Meteorological direction is where the wind comes *from*: a westerly (270°) blows to the right.
    """
    if not speed_kmh or direction_deg is None:
        return 0.0
    try:
        dx = -math.sin(math.radians(float(direction_deg)))
        return max(-1.0, min(1.0, dx * float(speed_kmh) / 50.0))
    except (TypeError, ValueError):
        return 0.0


class SkyBackground(_Area):
    """Gradient sky with lightweight particle effects (rain, snow, hail, stars, clouds, sun rays)."""

    FRAME_US = 33_000       # ~30 fps for precipitation
    SLOW_FRAME_US = 66_000  # ~15 fps for slow scenes (stars, sun rays, clouds only)

    # particle counts per intensity (light, moderate, heavy)
    RAIN_COUNT = (45, 110, 190)
    STORM_COUNT = (130, 160, 220)
    SNOW_COUNT = (50, 110, 190)

    def __init__(self):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_can_target(False)
        self.kind = "clear"
        self.is_day = True
        self.intensity = 1
        self.variant = None
        self.wind = 0.0
        self._aspect = 0.6  # height / width, updated on draw
        self._state = None
        self._rng = random.Random(7)
        self._tick_id = 0
        self._last = 0
        self._last_draw = 0
        self._t = 0.0
        self._flash = 0.0
        self._particles = []
        self._hail = []
        self._clouds = []
        self._stars = [(self._rng.random(), self._rng.random() * 0.6, self._rng.random() * 6.28,
                        0.6 + self._rng.random() * 1.2) for _ in range(90)]
        settings = Gtk.Settings.get_default()
        self._animations = settings.props.gtk_enable_animations if settings else True
        if settings:
            settings.connect("notify::gtk-enable-animations", self._on_anim_setting)

    def _on_anim_setting(self, settings, _pspec):
        self._animations = settings.props.gtk_enable_animations
        self._update_tick()

    def set_condition(self, kind, is_day, intensity=1, variant=None, wind=0.0):
        # Wind alone changes often between refreshes; adjust it without reseeding particles.
        self.wind = wind
        state = (kind, is_day, intensity, variant)
        if state == self._state:
            self.queue_draw()
            return
        self._state = state
        self.kind, self.is_day, self.intensity, self.variant = kind, is_day, intensity, variant
        rng = self._rng
        lvl = max(0, min(2, intensity))
        self._particles = []
        self._hail = []
        if kind in ("rain", "storm"):
            n = (self.STORM_COUNT if kind == "storm" else self.RAIN_COUNT)[lvl]
            speed = (0.75, 1.0, 1.25)[lvl]
            length = (0.7, 1.0, 1.3)[lvl]
            self._particles = [[rng.random(), rng.random(), (0.9 + rng.random() * 0.8) * speed,
                                (10 + rng.random() * 14) * length] for _ in range(n)]
            if variant == "hail":
                self._hail = [[rng.random(), rng.random(), 1.6 + rng.random() * 0.8,
                               1.2 + rng.random() * (1.0 + 0.6 * lvl)] for _ in range(20 + 15 * lvl)]
        elif kind == "snow":
            self._particles = [[rng.random(), rng.random(), 0.04 + rng.random() * 0.06,
                                1.2 + rng.random() * 2.4, rng.random() * 6.28]
                               for _ in range(self.SNOW_COUNT[lvl])]
        n_clouds = {"partly": 4, "cloudy": 7, "fog": 8, "rain": 5 + lvl, "storm": 6 + lvl,
                    "snow": 4 + lvl}.get(kind, 0)
        self._clouds = [[rng.random() * 1.4 - 0.2, rng.random() * 0.45, 0.18 + rng.random() * 0.22,
                         0.004 + rng.random() * 0.01] for _ in range(n_clouds)]
        self._update_tick()
        self.queue_draw()

    def _sunny(self):
        return self.is_day and self.kind in ("clear", "partly")

    def _wants_animation(self):
        return self._animations and (self._particles or self._clouds or self.kind in ("clear", "partly"))

    def _frame_us(self):
        return self.FRAME_US if self._particles else self.SLOW_FRAME_US

    def _update_tick(self):
        if self._wants_animation() and not self._tick_id:
            self._last = 0
            self._tick_id = self.add_tick_callback(self._on_tick)
        elif not self._wants_animation() and self._tick_id:
            self.remove_tick_callback(self._tick_id)
            self._tick_id = 0
            self.queue_draw()

    @staticmethod
    def _wrap_x(p):
        if p[0] > 1.1:
            p[0] -= 1.2
        elif p[0] < -0.1:
            p[0] += 1.2

    def _on_tick(self, _widget, clock):
        now = clock.get_frame_time()
        if self._last == 0:
            self._last = now
            return True
        if now - self._last_draw < self._frame_us():
            return True
        dt = min(0.1, (now - self._last) / 1e6)
        self._last = now
        self._last_draw = now
        self._t += dt
        drift = self._drift() * self._aspect  # screen slant -> normalized x per normalized y
        if self.kind in ("rain", "storm"):
            for p in self._particles:
                p[1] += p[2] * dt
                p[0] += p[2] * dt * drift
                if p[1] > 1.05:
                    p[1] = -0.05
                    p[0] = self._rng.random()
                self._wrap_x(p)
            for p in self._hail:
                p[1] += p[2] * dt
                p[0] += p[2] * dt * drift * 0.6
                if p[1] > 1.05:
                    p[1] = -0.05
                    p[0] = self._rng.random()
                self._wrap_x(p)
            if self.kind == "storm":
                self._flash = max(0.0, self._flash - dt * 2.5)
                if self._rng.random() < dt * (0.08, 0.12, 0.2)[max(0, min(2, self.intensity))]:
                    self._flash = 0.55
        elif self.kind == "snow":
            for p in self._particles:
                p[1] += p[2] * dt
                p[4] += dt
                p[0] += math.sin(p[4]) * 0.0008 + self.wind * 0.06 * dt * self._aspect
                if p[1] > 1.02:
                    p[1] = -0.02
                    p[0] = self._rng.random()
                self._wrap_x(p)
        cloud_dir = -1.0 if self.wind < -0.05 else 1.0
        cloud_boost = 1.0 + abs(self.wind) * 2.0
        for c in self._clouds:
            c[0] += c[3] * dt * cloud_dir * cloud_boost
            if cloud_dir > 0 and c[0] - c[2] > 1.2:
                c[0] = -c[2] - 0.2
            elif cloud_dir < 0 and c[0] + c[2] < -0.2:
                c[0] = 1.2 + c[2]
        self.queue_draw()
        return True

    def _drift(self):
        """Horizontal travel per unit of fall: a light baseline slant plus the wind."""
        return 0.08 + self.wind * 0.45 if abs(self.wind) > 0.02 else 0.08

    def draw(self, cr, w, h):
        self._aspect = h / max(w, 1)
        top, bottom = SKY.get((self.kind, self.is_day), SKY[("clear", True)])
        grad = cairo.LinearGradient(0, 0, 0, h)
        grad.add_color_stop_rgb(0, *top)
        grad.add_color_stop_rgb(1, *bottom)
        cr.set_source(grad)
        cr.paint()

        if self._sunny():
            sx, sy = w * 0.85, -h * 0.05
            reach = max(w, h) * 0.55
            glow = cairo.RadialGradient(sx, sy, 0, sx, sy, reach)
            glow.add_color_stop_rgba(0, 1, 0.97, 0.85, 0.45)
            glow.add_color_stop_rgba(1, 1, 0.97, 0.85, 0)
            cr.set_source(glow)
            cr.paint()
            # slowly turning, gently breathing sun rays
            strength = 0.07 if self.kind == "clear" else 0.04
            rays = cairo.RadialGradient(sx, sy, 0, sx, sy, reach * 1.25)
            rays.add_color_stop_rgba(0, 1, 0.98, 0.88, strength * (0.8 + 0.2 * math.sin(self._t * 0.6)))
            rays.add_color_stop_rgba(1, 1, 0.98, 0.88, 0)
            cr.set_source(rays)
            n = 14
            spin = self._t * 0.025
            for i in range(n):
                a = spin + i * 2 * math.pi / n
                cr.move_to(sx, sy)
                cr.arc(sx, sy, reach * 1.25, a, a + math.pi / n * 0.55)
                cr.close_path()
            cr.fill()

        if not self.is_day and self.kind in ("clear", "partly"):
            for x, y, phase, size in self._stars:
                a = 0.35 + 0.35 * math.sin(self._t * 1.3 + phase)
                cr.set_source_rgba(1, 1, 1, a)
                cr.arc(x * w, y * h, size, 0, 2 * math.pi)
                cr.fill()

        cloud_alpha = 0.10 if self.is_day else 0.06
        if self.kind == "fog":
            cloud_alpha = 0.16
        for cx, cy, r, _ in self._clouds:
            R = r * max(w, 400)
            g = cairo.RadialGradient(cx * w, cy * h, 0, cx * w, cy * h, R)
            g.add_color_stop_rgba(0, 1, 1, 1, cloud_alpha)
            g.add_color_stop_rgba(1, 1, 1, 1, 0)
            cr.set_source(g)
            cr.arc(cx * w, cy * h, R, 0, 2 * math.pi)
            cr.fill()

        if self.kind in ("rain", "storm"):
            slant = self._drift()  # matches the on-screen motion set up in _on_tick
            lvl = max(0, min(2, self.intensity))
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            if self.variant == "freezing":
                cr.set_line_width(1.4)
                cr.set_source_rgba(0.92, 0.97, 1.0, 0.45)
            else:
                cr.set_line_width((1.0, 1.2, 1.4)[lvl])
                cr.set_source_rgba(0.85, 0.9, 1.0, (0.26, 0.32, 0.38)[lvl])
            for x, y, _speed, length in self._particles:
                px, py = x * w, y * h
                cr.move_to(px, py)
                cr.line_to(px - length * slant, py - length)
            cr.stroke()
            if self.variant == "freezing":
                # tiny ice glints at the head of each drop
                cr.set_source_rgba(1, 1, 1, 0.55)
                for x, y, _speed, _length in self._particles[::3]:
                    cr.arc(x * w, y * h, 1.1, 0, 2 * math.pi)
                    cr.fill()
            if self._hail:
                cr.set_source_rgba(0.95, 0.97, 1.0, 0.8)
                for x, y, _speed, r in self._hail:
                    cr.arc(x * w, y * h, r, 0, 2 * math.pi)
                    cr.fill()
        elif self.kind == "snow":
            cr.set_source_rgba(1, 1, 1, 0.75)
            for x, y, _s, r, _ph in self._particles:
                cr.arc(x * w, y * h, r, 0, 2 * math.pi)
                cr.fill()

        if self._flash > 0:
            cr.set_source_rgba(0.9, 0.92, 1.0, self._flash * 0.5)
            cr.paint()


# ---------------------------------------------------------------------------
# small widgets for the forecast & tiles
# ---------------------------------------------------------------------------


class RangeBar(_Area):
    """Apple-style temperature range bar for the 10-day list."""

    def __init__(self, lo, hi, overall_lo, overall_hi, current=None):
        super().__init__(width=90, height=6)
        self.set_valign(Gtk.Align.CENTER)
        self.set_hexpand(True)
        self.lo, self.hi = lo, hi
        self.overall_lo, self.overall_hi = overall_lo, overall_hi
        self.current = current

    def draw(self, cr, w, h):
        span = (self.overall_hi - self.overall_lo) or 1
        rounded_rect(cr, 0, 0, w, h, h / 2)
        cr.set_source_rgba(0, 0, 0, 0.22)
        cr.fill()
        x0 = (self.lo - self.overall_lo) / span * w
        x1 = (self.hi - self.overall_lo) / span * w
        x1 = max(x1, x0 + h)
        grad = cairo.LinearGradient(x0, 0, x1, 0)
        grad.add_color_stop_rgb(0, *temp_color(self.lo))
        grad.add_color_stop_rgb(1, *temp_color(self.hi))
        rounded_rect(cr, x0, 0, x1 - x0, h, h / 2)
        cr.set_source(grad)
        cr.fill()
        if self.current is not None:
            cx = (min(max(self.current, self.overall_lo), self.overall_hi) - self.overall_lo) / span * w
            cx = min(max(cx, h / 2), w - h / 2)
            cr.set_source_rgba(0, 0, 0, 0.35)
            cr.arc(cx, h / 2, h / 2 + 1.5, 0, 2 * math.pi)
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.arc(cx, h / 2, h / 2, 0, 2 * math.pi)
            cr.fill()


class GradientBar(_Area):
    """A colored scale with a dot marking the value (UV index, AQI)."""

    def __init__(self, stops, vmin, vmax, value):
        super().__init__(height=6)
        self.set_hexpand(True)
        self.stops, self.vmin, self.vmax, self.value = stops, vmin, vmax, value

    def draw(self, cr, w, h):
        rounded_rect(cr, 0, 0, w, h, h / 2)
        cr.set_source(gradient_from_stops(0, w, self.stops, self.vmin, self.vmax))
        cr.fill()
        if self.value is None:
            return
        frac = min(1, max(0, (self.value - self.vmin) / ((self.vmax - self.vmin) or 1)))
        cx = min(max(frac * w, h / 2), w - h / 2)
        cr.set_source_rgba(0, 0, 0, 0.4)
        cr.arc(cx, h / 2, h / 2 + 1.5, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.arc(cx, h / 2, h / 2, 0, 2 * math.pi)
        cr.fill()


class SunArc(_Area):
    """A 24-hour sine curve with horizon line and the sun's current position."""

    def __init__(self, sunrise_h, sunset_h, now_h):
        super().__init__(height=56)
        self.set_hexpand(True)
        self.sunrise_h, self.sunset_h, self.now_h = sunrise_h, sunset_h, now_h

    def _y(self, hour, amp, mid):
        noon = (self.sunrise_h + self.sunset_h) / 2
        return mid + amp * math.cos(2 * math.pi * (hour - noon) / 24)

    def draw(self, cr, w, h):
        amp = h * 0.42
        mid = h * 0.5
        noon = (self.sunrise_h + self.sunset_h) / 2
        horizon = mid + amp * math.cos(2 * math.pi * (self.sunrise_h - noon) / 24)
        r, g, b = fg(self)

        # curve, dim below horizon, bright above
        def curve():
            cr.new_path()
            for i in range(0, 241):
                hr = i / 10
                x = hr / 24 * w
                y = 2 * mid - self._y(hr, amp, mid)  # invert so midday is up
                if i == 0:
                    cr.move_to(x, y)
                else:
                    cr.line_to(x, y)

        horizon_y = 2 * mid - horizon
        cr.set_line_width(2)
        cr.save()
        cr.rectangle(0, 0, w, horizon_y)
        cr.clip()
        curve()
        cr.set_source_rgba(r, g, b, 0.85)
        cr.stroke()
        cr.restore()
        cr.save()
        cr.rectangle(0, horizon_y, w, h - horizon_y)
        cr.clip()
        curve()
        cr.set_source_rgba(r, g, b, 0.3)
        cr.stroke()
        cr.restore()

        cr.set_line_width(1)
        cr.set_source_rgba(r, g, b, 0.45)
        cr.move_to(0, horizon_y)
        cr.line_to(w, horizon_y)
        cr.stroke()

        sx = self.now_h / 24 * w
        sy = 2 * mid - self._y(self.now_h, amp, mid)
        above = sy <= horizon_y
        if above:
            glow = cairo.RadialGradient(sx, sy, 0, sx, sy, 12)
            glow.add_color_stop_rgba(0, 1, 1, 0.85, 0.7)
            glow.add_color_stop_rgba(1, 1, 1, 0.85, 0)
            cr.set_source(glow)
            cr.arc(sx, sy, 12, 0, 2 * math.pi)
            cr.fill()
        cr.set_source_rgba(1, 1, 1, 1 if above else 0.55)
        cr.arc(sx, sy, 4.5, 0, 2 * math.pi)
        cr.fill()


class Compass(_Area):
    def __init__(self, direction, speed_text, unit_text, size=120):
        super().__init__(width=size, height=size)
        self.set_halign(Gtk.Align.CENTER)
        self.direction, self.speed_text, self.unit_text = direction, speed_text, unit_text

    def draw(self, cr, w, h):
        cx, cy = w / 2, h / 2
        R = min(w, h) / 2 - 2
        r, g, b = fg(self)
        # ticks
        for i in range(72):
            a = math.radians(i * 5) - math.pi / 2
            major = i % 18 == 0
            if major:
                continue  # leave room for letters
            inner = R - (6 if i % 6 == 0 else 4)
            cr.set_source_rgba(r, g, b, 0.75 if i % 6 == 0 else 0.35)
            cr.set_line_width(1.2 if i % 6 == 0 else 1)
            cr.move_to(cx + inner * math.cos(a), cy + inner * math.sin(a))
            cr.line_to(cx + R * math.cos(a), cy + R * math.sin(a))
            cr.stroke()
        for label, deg in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
            a = math.radians(deg) - math.pi / 2
            text(self, cr, label, cx + (R - 4) * math.cos(a), cy + (R - 4) * math.sin(a),
                 size=7.5, align="center", valign="middle", bold=True, alpha=0.9)
        # arrow: points where the wind is blowing *to*
        if self.direction is not None:
            a = math.radians(self.direction + 180) - math.pi / 2
            tip = R - 12
            tail = R - 12
            hx, hy = cx + tip * math.cos(a), cy + tip * math.sin(a)
            tx, ty = cx - tail * math.cos(a), cy - tail * math.sin(a)
            cr.set_source_rgba(r, g, b, 1)
            cr.set_line_width(2.5)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            # gap in the middle for the speed text
            gap = R * 0.42
            cr.move_to(tx, ty)
            cr.line_to(cx - gap * math.cos(a), cy - gap * math.sin(a))
            cr.move_to(cx + gap * math.cos(a), cy + gap * math.sin(a))
            cr.line_to(hx, hy)
            cr.stroke()
            # arrow head
            ah = 8
            for side in (-1, 1):
                aa = a + math.pi + side * 0.45
                cr.move_to(hx, hy)
                cr.line_to(hx + ah * math.cos(aa), hy + ah * math.sin(aa))
            cr.stroke()
            cr.arc(tx, ty, 3.5, 0, 2 * math.pi)
            cr.fill()
        text(self, cr, self.speed_text, cx, cy - 2, size=14, align="center", valign="bottom", bold=True)
        text(self, cr, self.unit_text, cx, cy - 2, size=7.5, align="center", valign="top", alpha=0.8)


class PressureGauge(_Area):
    def __init__(self, hpa, trend, value_text, unit_text, size=120):
        super().__init__(width=size, height=size)
        self.set_halign(Gtk.Align.CENTER)
        self.hpa, self.trend, self.value_text, self.unit_text = hpa, trend, value_text, unit_text

    def draw(self, cr, w, h):
        cx, cy = w / 2, h / 2
        R = min(w, h) / 2 - 2
        r, g, b = fg(self)
        start, sweep = math.radians(135), math.radians(270)
        lo, hi = 960, 1060
        n = 50
        frac = None if self.hpa is None else min(1, max(0, (self.hpa - lo) / (hi - lo)))
        for i in range(n + 1):
            a = start + sweep * i / n
            cr.set_source_rgba(r, g, b, 0.5)
            cr.set_line_width(1.2)
            cr.move_to(cx + (R - 8) * math.cos(a), cy + (R - 8) * math.sin(a))
            cr.line_to(cx + R * math.cos(a), cy + R * math.sin(a))
            cr.stroke()
        if frac is not None:
            a = start + sweep * frac
            cr.set_source_rgba(r, g, b, 1)
            cr.set_line_width(4)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.move_to(cx + (R - 12) * math.cos(a), cy + (R - 12) * math.sin(a))
            cr.line_to(cx + (R + 1) * math.cos(a), cy + (R + 1) * math.sin(a))
            cr.stroke()
        arrow = {1: "↑", -1: "↓", 0: "="}[self.trend]
        text(self, cr, arrow, cx, cy - 8, size=10, align="center", valign="bottom", alpha=0.85)
        text(self, cr, self.value_text, cx, cy - 8, size=12.5, align="center", valign="top", bold=True)
        text(self, cr, self.unit_text, cx, cy + 12, size=7.5, align="center", valign="top", alpha=0.8)
        text(self, cr, "Low", cx - R * 0.55, h - 4, size=7, align="center", valign="bottom", alpha=0.7)
        text(self, cr, "High", cx + R * 0.55, h - 4, size=7, align="center", valign="bottom", alpha=0.7)


class MoonDisc(_Area):
    def __init__(self, age, synodic=29.530588853, size=96):
        super().__init__(width=size, height=size)
        self.set_halign(Gtk.Align.CENTER)
        self.age, self.synodic = age, synodic

    def draw(self, cr, w, h):
        cx, cy = w / 2, h / 2
        R = min(w, h) / 2 - 3
        # dark side
        cr.set_source_rgba(0.08, 0.09, 0.12, 0.75)
        cr.arc(cx, cy, R, 0, 2 * math.pi)
        cr.fill()
        phase = self.age / self.synodic  # 0 new, .5 full
        k = math.cos(2 * math.pi * phase)  # 1 at new, -1 at full
        waxing = phase < 0.5
        cr.save()
        cr.translate(cx, cy)
        if not waxing:
            cr.scale(-1, 1)
        # lit limb: right half
        cr.new_path()
        cr.arc(0, 0, R, -math.pi / 2, math.pi / 2)
        # terminator: ellipse from bottom back to top
        sx = k if abs(k) > 1e-3 else 1e-3
        cr.save()
        cr.scale(sx, 1)
        cr.arc_negative(0, 0, R, math.pi / 2, -math.pi / 2)
        cr.restore()
        cr.close_path()
        grad = cairo.RadialGradient(-R * 0.3, -R * 0.3, R * 0.1, 0, 0, R)
        grad.add_color_stop_rgb(0, 0.98, 0.97, 0.92)
        grad.add_color_stop_rgb(1, 0.82, 0.81, 0.76)
        cr.set_source(grad)
        cr.fill()
        cr.restore()
        cr.set_source_rgba(1, 1, 1, 0.25)
        cr.set_line_width(1)
        cr.arc(cx, cy, R, 0, 2 * math.pi)
        cr.stroke()


class PrecipBars(_Area):
    """15-minute precipitation intensity for the next two hours."""

    def __init__(self, values, labels):
        super().__init__(height=70)
        self.set_hexpand(True)
        self.values, self.labels = values, labels

    def draw(self, cr, w, h):
        chart_h = h - 16
        vmax = max(2.0, max(self.values or [0]))
        n = max(1, len(self.values))
        bw = w / n
        r, g, b = fg(self)
        cr.set_source_rgba(r, g, b, 0.2)
        cr.set_line_width(1)
        for frac in (0.33, 0.66):
            cr.move_to(0, chart_h * frac)
            cr.line_to(w, chart_h * frac)
        cr.stroke()
        for i, v in enumerate(self.values):
            bh = max(2, min(1, v / vmax) * chart_h) if v > 0 else 2
            rounded_rect(cr, i * bw + 3, chart_h - bh, bw - 6, bh, 3)
            cr.set_source_rgba(0.55, 0.78, 1.0, 0.95 if v > 0 else 0.25)
            cr.fill()
        for i, lab in self.labels:
            text(self, cr, lab, i * bw, h, size=7.5, align="left", valign="bottom", alpha=0.8)


# ---------------------------------------------------------------------------
# interactive line / bar chart used by the detail dialog
# ---------------------------------------------------------------------------


class LineChart(_Area):
    """Plots one day of hourly data with hover readout.

    series: list of dicts with keys
        values: list[float|None]
        style: "line" | "bar" | "dash"
        color: (r, g, b) or "temp" (gradient by temperature in °C via `temp_c`)
        label: str (legend)
        temp_c: list[float] (only for color == "temp")
    """

    LEFT, RIGHT, TOP, BOTTOM = 6, 44, 30, 24

    def __init__(self):
        super().__init__(height=240)
        self.set_hexpand(True)
        self.hours = []
        self.series = []
        self.y_fmt = lambda v: f"{v:g}"
        self.hover_fmt = None
        self.y_min = None
        self.y_max = None
        self.now_frac = None
        self.hover = None
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

    def set_data(self, hours, series, y_fmt=None, hover_fmt=None, y_min=None, y_max=None, now_frac=None):
        self.hours, self.series = hours, series
        self.y_fmt = y_fmt or (lambda v: f"{v:g}")
        self.hover_fmt = hover_fmt
        self.y_min, self.y_max, self.now_frac = y_min, y_max, now_frac
        self.hover = None
        self.queue_draw()

    def _on_motion(self, _ctl, x, _y):
        w = self.get_width()
        n = len(self.hours)
        if n < 2:
            return
        plot_w = w - self.LEFT - self.RIGHT
        frac = (x - self.LEFT) / plot_w
        idx = int(round(frac * (n - 1)))
        idx = min(max(idx, 0), n - 1)
        if idx != self.hover:
            self.hover = idx
            self.queue_draw()

    def _on_leave(self, _ctl):
        self.hover = None
        self.queue_draw()

    def _range(self):
        vals = [v for s in self.series for v in s["values"] if v is not None]
        if not vals:
            return 0, 1
        lo = min(vals) if self.y_min is None else min(self.y_min, min(vals))
        hi = max(vals) if self.y_max is None else max(self.y_max, max(vals))
        if hi - lo < 1e-6:
            hi = lo + 1
        ticks = nice_ticks(lo, hi)
        return ticks[0], ticks[-1]

    def draw(self, cr, w, h):
        n = len(self.hours)
        if n < 2 or not self.series:
            text(self, cr, "No data", w / 2, h / 2, align="center", valign="middle", alpha=0.6)
            return
        r, g, b = fg(self)
        L, R, T, B = self.LEFT, self.RIGHT, self.TOP, self.BOTTOM
        pw, ph = w - L - R, h - T - B
        lo, hi = self._range()

        def X(i):
            return L + pw * i / (n - 1)

        def Y(v):
            return T + ph * (1 - (v - lo) / (hi - lo))

        # grid + y labels
        cr.set_line_width(1)
        for t in nice_ticks(lo, hi):
            y = Y(t)
            cr.set_source_rgba(r, g, b, 0.12)
            cr.move_to(L, y)
            cr.line_to(L + pw, y)
            cr.stroke()
            text(self, cr, self.y_fmt(t), L + pw + 6, y, size=8, valign="middle", alpha=0.65)
        # x labels every 6 hours
        for i, dt in enumerate(self.hours):
            if dt.hour % 6 == 0:
                x = X(i)
                cr.set_source_rgba(r, g, b, 0.12)
                cr.move_to(x, T)
                cr.line_to(x, T + ph)
                cr.stroke()
                if i < n - 1:
                    text(self, cr, self._hour_label(dt), x + 2, h - 2, size=8, valign="bottom", alpha=0.65)

        bar_w = pw / n * 0.6
        for s in self.series:
            vals = s["values"]
            style = s.get("style", "line")
            color = s.get("color", (0.4, 0.7, 1.0))
            if style == "bar":
                for i, v in enumerate(vals):
                    if not v:
                        continue
                    x = X(i) - bar_w / 2
                    y0 = Y(max(lo, 0))
                    rounded_rect(cr, x, Y(v), bar_w, max(1.5, y0 - Y(v)), 2)
                    cr.set_source_rgba(*color, 0.9)
                    cr.fill()
                continue
            pts = [(X(i), Y(v)) for i, v in enumerate(vals) if v is not None]
            if len(pts) < 2:
                continue
            if color == "temp":
                tc = s.get("temp_c") or vals
                grad = cairo.LinearGradient(0, T + ph, 0, T)
                t_lo, t_hi = min(tc), max(tc)
                for k in range(5):
                    f = k / 4
                    grad.add_color_stop_rgb(f, *temp_color(t_lo + (t_hi - t_lo) * f))
                stroke_src = grad
                fill_rgb = temp_color(sum(tc) / len(tc))
            else:
                stroke_src = cairo.SolidPattern(*color)
                fill_rgb = color
            self._smooth_path(cr, pts)
            if style == "line" and s.get("fill", True):
                cr.line_to(pts[-1][0], T + ph)
                cr.line_to(pts[0][0], T + ph)
                cr.close_path()
                fill = cairo.LinearGradient(0, T, 0, T + ph)
                fill.add_color_stop_rgba(0, *fill_rgb, 0.35)
                fill.add_color_stop_rgba(1, *fill_rgb, 0.0)
                cr.set_source(fill)
                cr.fill()
                self._smooth_path(cr, pts)
            cr.set_source(stroke_src)
            cr.set_line_width(2.5 if style == "line" else 1.8)
            cr.set_dash([5, 4] if style == "dash" else [])
            cr.stroke()
            cr.set_dash([])

        # past-time shading
        if self.now_frac is not None and 0 < self.now_frac < 1:
            nx = L + pw * self.now_frac
            cr.set_source_rgba(0, 0, 0, 0.18)
            cr.rectangle(L, T, nx - L, ph)
            cr.fill()
            cr.set_source_rgba(r, g, b, 0.7)
            cr.set_line_width(1)
            cr.move_to(nx, T - 4)
            cr.line_to(nx, T + ph)
            cr.stroke()

        # legend (hidden while the hover readout occupies the top strip)
        x = L
        for s in (self.series if self.hover is None else []):
            if not s.get("label"):
                continue
            color = s.get("color")
            if color == "temp":
                color = (1.0, 0.75, 0.3)
            cr.set_source_rgb(*color)
            rounded_rect(cr, x, 6, 10, 10, 3)
            cr.fill()
            tw, _ = text(self, cr, s["label"], x + 14, 4, size=8, alpha=0.8)
            x += tw + 28

        # hover readout
        if self.hover is not None:
            i = self.hover
            hx = X(i)
            cr.set_source_rgba(r, g, b, 0.8)
            cr.set_line_width(1)
            cr.move_to(hx, T)
            cr.line_to(hx, T + ph)
            cr.stroke()
            for s in self.series:
                v = s["values"][i] if i < len(s["values"]) else None
                if v is None or s.get("style") == "bar":
                    continue
                cr.set_source_rgb(1, 1, 1)
                cr.arc(hx, Y(v), 4.5, 0, 2 * math.pi)
                cr.fill()
                c = s.get("color")
                if c == "temp":
                    c = temp_color((s.get("temp_c") or s["values"])[i])
                cr.set_source_rgb(*c)
                cr.arc(hx, Y(v), 3, 0, 2 * math.pi)
                cr.fill()
            label = self.hover_fmt(i) if self.hover_fmt else ""
            if label:
                layout_w = len(label) * 6.5 + 16
                bx = min(max(hx - layout_w / 2, 0), w - layout_w)
                rounded_rect(cr, bx, 0, layout_w, 22, 6)
                cr.set_source_rgba(0.12, 0.12, 0.14, 0.9)
                cr.fill()
                text(self, cr, label, bx + layout_w / 2, 11, size=8.5, align="center", valign="middle",
                     color=(1, 1, 1), bold=True)

    def _hour_label(self, dt):
        from .text import is_24h
        units = getattr(self, "units", None)
        if units is not None and is_24h(units):
            return f"{dt.hour:02d}"
        h = dt.hour % 12 or 12
        return f"{h}{'a' if dt.hour < 12 else 'p'}"

    @staticmethod
    def _smooth_path(cr, pts):
        cr.new_path()
        cr.move_to(*pts[0])
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            mx = (x0 + x1) / 2
            cr.curve_to(mx, y0, mx, y1, x1, y1)
