"""The scrolling weather page shown for one location."""

from datetime import datetime

from gi.repository import Gtk, Pango

from . import astro, codes, drawing, text


def label(s, *classes, xalign=0.0, wrap=False, ellipsize=False, **kw):
    lbl = Gtk.Label(label=s, xalign=xalign, **kw)
    for c in classes:
        lbl.add_css_class(c)
    if wrap:
        lbl.set_wrap(True)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lbl.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
    if ellipsize:
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
    return lbl


def clear(box):
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def card_title(title, icon=None):
    row = Gtk.Box(spacing=6)
    if icon:
        img = Gtk.Image.new_from_icon_name(icon)
        img.set_pixel_size(12)
        img.add_css_class("card-title")
        row.append(img)
    row.append(label(title.upper(), "card-title"))
    return row


def make_card(title=None, icon=None, on_click=None, tooltip=None):
    """Returns (widget, body). Clickable cards are flat buttons (keyboard accessible)."""
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    if title:
        body.append(card_title(title, icon))
    if on_click:
        btn = Gtk.Button(child=body)
        btn.add_css_class("flat")
        btn.add_css_class("wx-card")
        btn.connect("clicked", lambda *_: on_click())
        if tooltip:
            btn.set_tooltip_text(tooltip)
        return btn, body
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.add_css_class("wx-card")
    box.append(body)
    return box, body


def sep():
    s = Gtk.Separator()
    s.add_css_class("wx-sep")
    return s


class WeatherView(Gtk.Box):
    """Persistent container; `update()` rebuilds the content for new data."""

    def __init__(self, on_detail):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.add_css_class("weather-view")
        self.set_margin_top(8)
        self.set_margin_bottom(24)
        self.set_margin_start(14)
        self.set_margin_end(14)
        self.on_detail = on_detail

        self.hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, halign=Gtk.Align.CENTER)
        self.hero.set_margin_top(12)
        self.hero.set_margin_bottom(18)
        self.top_slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.left.set_size_request(340, -1)
        self.right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, hexpand=True)
        self.columns.append(self.left)
        self.columns.append(self.right)
        self.footer = label("", "tile-caption", "dim", xalign=0.5)
        for w in (self.hero, self.top_slot, self.columns, self.footer):
            self.append(w)

    # ------------------------------------------------------------------
    def set_narrow(self, narrow):
        self.columns.set_orientation(Gtk.Orientation.VERTICAL if narrow else Gtk.Orientation.HORIZONTAL)
        self.left.set_size_request(-1 if narrow else 340, -1)

    def update(self, loc, w, units):
        self.units = units
        self.w = w
        for box in (self.hero, self.top_slot, self.left, self.right):
            clear(box)
        self._hero(loc, w, units)
        nh = self._next_hour(w, units)
        if nh:
            self.top_slot.append(nh)
        self.top_slot.append(self._hourly(w, units))
        self.left.append(self._daily(w, units))
        aq = self._air_quality(w, units)
        if aq:
            self.right.append(aq)
        self.right.append(self._tiles(w, units))
        if w.fetched:
            upd = datetime.fromtimestamp(w.fetched)  # the user's own clock, not the location's
            self.footer.set_label(f"Updated {text.fmt_time(upd, units)} · Weather data by Open-Meteo.com")

    # ------------------------------------------------------------------
    def _hero(self, loc, w, units):
        code = w.c("weather_code", 0)
        d0 = w.today_index()
        if loc.is_current:
            row = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER)
            img = Gtk.Image.new_from_icon_name("find-location-symbolic")
            img.set_pixel_size(12)
            row.append(img)
            row.append(label("MY LOCATION", "card-title"))
            self.hero.append(row)
        self.hero.append(label(loc.name, "hero-name", xalign=0.5, wrap=True, justify=Gtk.Justification.CENTER))
        self.hero.append(label(units.temp(w.c("temperature_2m")), "hero-temp", xalign=0.5))
        self.hero.append(label(codes.describe(code), "hero-cond", xalign=0.5))
        hi, lo = w.d("temperature_2m_max", d0), w.d("temperature_2m_min", d0)
        self.hero.append(label(f"H:{units.temp(hi)}  L:{units.temp(lo)}", "hero-hilo", xalign=0.5))

    # ------------------------------------------------------------------
    def _next_hour(self, w, units):
        nh = text.next_hour_precip(w)
        if not nh:
            return None
        headline, values, start = nh
        card, body = make_card("Next-Hour Precipitation", "weather-showers-symbolic",
                               on_click=lambda: self.on_detail("precipitation", w.today_index()))
        body.append(label(headline, "tile-sub", wrap=True))
        labels = []
        for i in range(0, len(values), 2):
            if i == 0:
                labels.append((i, "Now"))
            else:
                labels.append((i, f"{i * 15}m"))
        body.append(drawing.PrecipBars(values, labels))
        return card

    # ------------------------------------------------------------------
    def _hourly(self, w, units):
        card, body = make_card(None, on_click=lambda: self.on_detail("temperature", w.today_index()),
                               tooltip="Show hourly details")
        body.append(label(text.hourly_summary(w, units), "tile-caption", wrap=True))
        body.append(sep())
        scroller = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.NEVER,
                                      hscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        scroller.set_propagate_natural_height(True)
        scroller.add_css_class("hourly-scroller")
        row = Gtk.Box(spacing=4)
        row.set_margin_bottom(10)
        scroller.set_child(row)
        body.append(scroller)

        i0 = w.hour_index()
        end = min(w.n_hours(), i0 + 25)
        # sunrise/sunset events in the window
        events = []
        t_start = w.h("time", i0, 0)
        t_end = w.h("time", end - 1, 0) + 3600
        for d in range(w.n_days()):
            for key, name, icon in (("sunrise", "Sunrise", "daytime-sunrise-symbolic"),
                                    ("sunset", "Sunset", "daytime-sunset-symbolic")):
                t = w.d(key, d)
                if t and max(t_start, w.now()) <= t < t_end:
                    events.append((t, name, icon))

        def column(top, icon, mid, bottom, is_event=False):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            col.set_size_request(54, -1)
            col.append(label(top, "hour-time", xalign=0.5))
            img = Gtk.Image.new_from_icon_name(icon)
            img.set_pixel_size(24)
            img.set_margin_top(2)
            col.append(img)
            col.append(label(mid, "precip-chance", xalign=0.5))
            col.append(label(bottom, "hour-temp" if not is_event else "hour-event", xalign=0.5))
            return col

        for i in range(i0, end):
            t = w.h("time", i)
            if i == i0:
                code = w.c("weather_code", w.h("weather_code", i))
                temp = w.c("temperature_2m", w.h("temperature_2m", i))
                is_day = w.is_day
                top = "Now"
            else:
                code = w.h("weather_code", i)
                temp = w.h("temperature_2m", i)
                is_day = bool(w.h("is_day", i, 1))
                top = text.fmt_hour(w.local(t), units)
            pop = w.h("precipitation_probability", i, 0)
            mid = f"{round(pop / 10) * 10}%" if pop >= 20 and codes.kind(code) in ("rain", "snow", "storm") else ""
            row.append(column(top, codes.icon(code, is_day), mid, units.temp(temp)))
            for et, name, icon in [e for e in events if t <= e[0] < t + 3600]:
                row.append(column(text.fmt_time(w.local(et), units), icon, "", name, is_event=True))
        return card

    # ------------------------------------------------------------------
    def _daily(self, w, units):
        card, body = make_card("10-Day Forecast", "x-office-calendar-symbolic")
        d0 = w.today_index()
        days = list(range(d0, min(w.n_days(), d0 + 10)))
        lows = [w.d("temperature_2m_min", d, 0) for d in days]
        highs = [w.d("temperature_2m_max", d, 0) for d in days]
        overall_lo, overall_hi = min(lows + [w.c("temperature_2m", 0)]), max(highs + [w.c("temperature_2m", 0)])
        for n, d in enumerate(days):
            body.append(sep())
            dt = w.local(w.d("time", d))
            name = "Today" if d == d0 else dt.strftime("%a")
            code = w.d("weather_code", d)
            pop = w.d("precipitation_probability_max", d, 0)

            row = Gtk.Box(spacing=10)
            row.append(label(name, "day-name", xalign=0, width_chars=6))
            icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            icon_box.set_size_request(36, -1)
            img = Gtk.Image.new_from_icon_name(codes.icon(code, True))
            img.set_pixel_size(22)
            icon_box.append(img)
            if pop >= 30 and codes.kind(code) in ("rain", "snow", "storm"):
                icon_box.append(label(f"{round(pop / 10) * 10}%", "precip-chance", xalign=0.5))
            icon_box.set_tooltip_text(codes.describe(code))
            row.append(icon_box)
            row.append(label(units.temp(lows[n]), "day-temp", "dim", xalign=1, width_chars=4))
            current = w.c("temperature_2m") if d == d0 else None
            row.append(drawing.RangeBar(lows[n], highs[n], overall_lo, overall_hi, current))
            row.append(label(units.temp(highs[n]), "day-temp", xalign=1, width_chars=4))

            btn = Gtk.Button(child=row)
            btn.add_css_class("flat")
            btn.add_css_class("day-row")
            btn.set_tooltip_text(f"{dt.strftime('%A')}: {codes.describe(code)}")
            btn.connect("clicked", lambda _b, d=d: self.on_detail("temperature", d))
            body.append(btn)
        return card

    # ------------------------------------------------------------------
    def _air_quality(self, w, units):
        if not w.air:
            return None
        key = "us_aqi" if units.aqi == "us" else "european_aqi"
        val = w.air_value(key)
        if val is None:
            return None
        cat, desc = text.aqi_category(val, units.aqi)
        card, body = make_card("Air Quality", "weather-windy-symbolic",
                               on_click=lambda: self.on_detail("aqi", w.today_index()))
        body.append(label(f"{round(val)}", "tile-value"))
        body.append(label(cat, "tile-sub"))
        stops = drawing.US_AQI_STOPS if units.aqi == "us" else drawing.EU_AQI_STOPS
        vmax = 300 if units.aqi == "us" else 100
        body.append(drawing.GradientBar(stops, 0, vmax, val))
        body.append(label(desc, "tile-caption", wrap=True))
        parts = []
        for k, name in (("pm2_5", "PM2.5"), ("pm10", "PM10"), ("ozone", "O₃"), ("nitrogen_dioxide", "NO₂")):
            v = w.air_value(k)
            if v is not None:
                parts.append(f"{name} {round(v)}")
        if parts:
            body.append(label(" · ".join(parts) + " µg/m³", "tile-caption", "dim", wrap=True))
        return card

    # ------------------------------------------------------------------
    def _tile(self, title, icon, metric, *children):
        d0 = self.w.today_index()
        card, body = make_card(title, icon, on_click=(lambda: self.on_detail(metric, d0)) if metric else None)
        card.set_size_request(150, 168)
        for c in children:
            if c is None:
                continue
            body.append(c)
        return card

    def _tiles(self, w, units):
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           min_children_per_line=2, max_children_per_line=3,
                           row_spacing=14, column_spacing=14)
        flow.set_valign(Gtk.Align.START)
        tiles = []
        i0 = w.hour_index()
        d0 = w.today_index()

        # UV
        uv = w.c("uv_index", w.h("uv_index", i0, 0))
        tiles.append(self._tile(
            "UV Index", "weather-clear-symbolic", "uv",
            label(f"{round(uv)}", "tile-value"),
            label(text.uv_level(uv), "tile-sub"),
            drawing.GradientBar(drawing.UV_STOPS, 0, 11, uv),
            Gtk.Box(vexpand=True),
            label(text.uv_advice(w, units), "tile-caption", wrap=True)))

        # Sunrise / sunset
        now = w.now()
        sr, ss = w.d("sunrise", d0), w.d("sunset", d0)
        if sr and ss:
            if now < sr:
                title, main_t, other = "Sunrise", sr, f"Sunset: {text.fmt_time(w.local(ss), units)}"
                icon = "daytime-sunrise-symbolic"
            elif now < ss:
                title, main_t = "Sunset", ss
                nsr = w.d("sunrise", d0 + 1)
                other = f"Sunrise: {text.fmt_time(w.local(nsr), units)}" if nsr else ""
                icon = "daytime-sunset-symbolic"
            else:
                nsr, nss = w.d("sunrise", d0 + 1), w.d("sunset", d0 + 1)
                title, main_t = "Sunrise", nsr or sr
                other = f"Sunset: {text.fmt_time(w.local(nss), units)}" if nss else ""
                icon = "daytime-sunrise-symbolic"
            lsr, lss, lnow = w.local(sr), w.local(ss), w.local(now)
            hours = lambda dt: dt.hour + dt.minute / 60  # noqa: E731
            daylen = w.d("daylight_duration", d0)
            tiles.append(self._tile(
                title, icon, None,
                label(text.fmt_time(w.local(main_t), units), "tile-value-sm"),
                drawing.SunArc(hours(lsr), hours(lss), hours(lnow)),
                Gtk.Box(vexpand=True),
                label(other, "tile-caption", wrap=True),
                label(f"Daylight: {text.fmt_duration(daylen)}" if daylen else "", "tile-caption", "dim")))

        # Wind
        ws, wd, wg = w.c("wind_speed_10m"), w.c("wind_direction_10m"), w.c("wind_gusts_10m")
        speed_txt = f"{round(units.wind_value(ws))}" if ws is not None else "--"
        _, bname = text.beaufort(ws or 0)
        tiles.append(self._tile(
            "Wind", "weather-windy-symbolic", "wind",
            drawing.Compass(wd, speed_txt, units.wind_label(), size=110),
            label(f"Gusts {units.wind(wg)} · from {text.wind_direction_name(wd)}", "tile-caption", wrap=True),
            label(bname, "tile-caption", "dim")))

        # Precipitation
        past, nxt = text.precipitation_texts(w, units)
        tiles.append(self._tile(
            "Precipitation", "weather-showers-symbolic", "precipitation",
            label(units.precip(past), "tile-value"),
            label("in last 24h", "tile-sub"),
            Gtk.Box(vexpand=True),
            label(nxt, "tile-caption", wrap=True)))

        # Feels like
        tiles.append(self._tile(
            "Feels Like", None, "temperature",
            label(units.temp(w.c("apparent_temperature")), "tile-value"),
            Gtk.Box(vexpand=True),
            label(text.feels_like_text(w), "tile-caption", wrap=True)))

        # Humidity
        hum = w.c("relative_humidity_2m")
        tiles.append(self._tile(
            "Humidity", "weather-fog-symbolic", "humidity",
            label(f"{round(hum)}%" if hum is not None else "--", "tile-value"),
            Gtk.Box(vexpand=True),
            label(text.humidity_text(w, units), "tile-caption", wrap=True)))

        # Visibility
        vis = w.c("visibility", w.h("visibility", i0))
        tiles.append(self._tile(
            "Visibility", "view-reveal-symbolic", "visibility",
            label(units.distance(vis), "tile-value"),
            Gtk.Box(vexpand=True),
            label(text.visibility_text(vis), "tile-caption", wrap=True)))

        # Pressure
        p = w.c("pressure_msl")
        trend = text.pressure_trend(w)
        tiles.append(self._tile(
            "Pressure", None, "pressure",
            drawing.PressureGauge(p, trend, units.pressure(p), units.pressure_unit, size=110),
            label(text.pressure_text(trend), "tile-caption", wrap=True)))

        # Moon
        m = astro.moon_info(now)
        nf = round(m["next_full"])
        full_txt = "Full moon today" if nf in (0, 30) else f"Full moon in {nf} day{'s' if nf != 1 else ''}"
        tiles.append(self._tile(
            m["phase"], "weather-clear-night-symbolic", None,
            drawing.MoonDisc(m["age"], size=84),
            label(f"Illumination {round(m['illumination'] * 100)}%", "tile-caption"),
            label(full_txt, "tile-caption", "dim")))

        for t in tiles:
            flow.append(t)
        return flow
