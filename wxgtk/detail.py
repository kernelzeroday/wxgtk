"""'Conditions' dialog: per-day hourly charts for each metric."""

from gi.repository import Adw, Gtk

from . import codes, drawing, text
from .view import clear, label

METRICS = [
    ("temperature", "Temperature"),
    ("precipitation", "Precipitation"),
    ("wind", "Wind"),
    ("humidity", "Humidity"),
    ("uv", "UV Index"),
    ("visibility", "Visibility"),
    ("pressure", "Pressure"),
    ("aqi", "Air Quality"),
]

BLUE = (0.35, 0.65, 1.0)
TEAL = (0.30, 0.80, 0.80)
GREY = (0.62, 0.65, 0.70)
VIOLET = (0.70, 0.55, 1.0)


class DetailDialog(Adw.Dialog):
    def __init__(self, weather, units, location_name, metric="temperature", day=None):
        super().__init__(title="Conditions", content_width=760, content_height=640)
        self.w = weather
        self.units = units
        self.metrics = [m for m in METRICS if m[0] != "aqi" or weather.air]
        self.metric = metric if any(m[0] == metric for m in self.metrics) else "temperature"
        self.day = weather.today_index() if day is None else day

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.dropdown = Gtk.DropDown.new_from_strings([m[1] for m in self.metrics])
        self.dropdown.set_selected([m[0] for m in self.metrics].index(self.metric))
        self.dropdown.connect("notify::selected", self._on_metric)
        self.dropdown.set_tooltip_text("Metric")
        header.set_title_widget(Adw.WindowTitle(title=location_name, subtitle=""))
        header.pack_start(self.dropdown)
        self.title_widget = header.get_title_widget()
        toolbar.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.set_margin_bottom(18)
        content.set_margin_top(6)

        # day strip
        strip = Gtk.Box(spacing=4, homogeneous=True)
        strip.add_css_class("day-strip")
        self.day_buttons = []
        group = None
        d0 = weather.today_index()
        for d in range(d0, min(weather.n_days(), d0 + 10)):
            dt = weather.local(weather.d("time", d))
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.append(label(dt.strftime("%a")[0], "caption", "dim", xalign=0.5))
            box.append(label(str(dt.day), "heading", xalign=0.5))
            btn = Gtk.ToggleButton(child=box)
            btn.add_css_class("flat")
            btn.add_css_class("circular-day")
            btn.set_tooltip_text(dt.strftime("%A, %B %-d"))
            if group:
                btn.set_group(group)
            else:
                group = btn
            btn.set_active(d == self.day)
            btn.connect("toggled", self._on_day, d)
            strip.append(btn)
            self.day_buttons.append(btn)
        sw = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.NEVER)
        sw.set_child(strip)
        sw.set_propagate_natural_height(True)
        content.append(sw)

        self.headline = label("", "title-1")
        self.subhead = label("", "dim", wrap=True)
        content.append(self.headline)
        content.append(self.subhead)

        self.chart = drawing.LineChart()
        self.chart.units = units
        self.chart.set_size_request(-1, 260)
        frame = Gtk.Box()
        frame.add_css_class("card")
        frame.add_css_class("chart-card")
        frame.append(self.chart)
        content.append(frame)

        content.append(label("Daily Summary", "heading"))
        self.summary = label("", wrap=True)
        content.append(self.summary)
        self.facts = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                 min_children_per_line=2, max_children_per_line=4,
                                 row_spacing=8, column_spacing=8)
        content.append(self.facts)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.set_child(content)
        scroller.set_propagate_natural_height(True)
        toolbar.set_content(scroller)
        self.set_child(toolbar)
        self.refresh()

    # ------------------------------------------------------------------
    def _on_metric(self, dd, _pspec):
        self.metric = self.metrics[dd.get_selected()][0]
        self.refresh()

    def _on_day(self, btn, d):
        if btn.get_active():
            self.day = d
            self.refresh()

    def _fact(self, title, value):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("card")
        box.add_css_class("fact")
        box.append(label(title, "caption", "dim"))
        box.append(label(value, "title-4"))
        return box

    # ------------------------------------------------------------------
    def refresh(self):
        w, u, d = self.w, self.units, self.day
        dt = w.local(w.d("time", d))
        self.title_widget.set_subtitle(dt.strftime("%A, %B %-d"))
        clear(self.facts)
        s, e = w.day_hour_range(d)
        idx = list(range(s, e))
        hours = [w.local(w.h("time", i)) for i in idx]
        now_frac = None
        if d == w.today_index() and len(idx) > 1:
            t0, t1 = w.h("time", idx[0]), w.h("time", idx[-1])
            now_frac = (w.now() - t0) / (t1 - t0)

        def hv(key, conv=lambda v: v):
            return [None if w.h(key, i) is None else conv(w.h(key, i)) for i in idx]

        def hfmt(fn):
            return lambda i: f"{text.fmt_hour(hours[i], u)} · {fn(i)}"

        m = self.metric
        facts = []
        if m == "temperature":
            temps_c = hv("temperature_2m")
            temps = [u.temp_value(v) if v is not None else None for v in temps_c]
            feels = hv("apparent_temperature", u.temp_value)
            hi, lo = w.d("temperature_2m_max", d), w.d("temperature_2m_min", d)
            self.headline.set_label(f"{u.temp(hi)} / {u.temp(lo)}" if d != w.today_index()
                                    else f"{u.temp(w.c('temperature_2m'))}")
            self.subhead.set_label(f"H:{u.temp(hi)}  L:{u.temp(lo)} · {codes.describe(w.d('weather_code', d))}")
            self.chart.set_data(hours, [
                {"values": temps, "color": "temp", "temp_c": [v if v is not None else 0 for v in temps_c],
                 "label": "Temperature"},
                {"values": feels, "style": "dash", "color": GREY, "label": "Feels like", "fill": False},
            ], y_fmt=lambda v: f"{round(v)}°",
                hover_fmt=hfmt(lambda i: f"{round(temps[i])}° (feels {round(feels[i])}°)"), now_frac=now_frac)
            fhi, flo = w.d("apparent_temperature_max", d), w.d("apparent_temperature_min", d)
            self.summary.set_label(
                f"{codes.describe(w.d('weather_code', d))}. The high will be {u.temp(hi)} and the low "
                f"{u.temp(lo)}. It will feel like {u.temp(flo)} to {u.temp(fhi)}.")
            facts = [("High", u.temp(hi)), ("Low", u.temp(lo)), ("Feels-like high", u.temp(fhi)),
                     ("Feels-like low", u.temp(flo))]

        elif m == "precipitation":
            mm = hv("precipitation")
            conv = (lambda v: v / 25.4) if u.precip_unit == "in" else (lambda v: v)
            vals = [conv(v or 0) for v in mm]
            pop = hv("precipitation_probability")
            total = w.d("precipitation_sum", d, 0)
            maxp = w.d("precipitation_probability_max", d, 0)
            self.headline.set_label(u.precip(total))
            self.subhead.set_label(f"Total for the day · {round(maxp)}% chance")
            unit = "″" if u.precip_unit == "in" else " mm"
            self.chart.set_data(hours, [{"values": vals, "style": "bar", "color": BLUE, "label": "Precipitation"}],
                                y_fmt=lambda v: f"{v:g}{unit}" if v else "0",
                                hover_fmt=hfmt(lambda i: f"{u.precip(mm[i] or 0)} · {round(pop[i] or 0)}%"),
                                y_min=0, y_max=conv(1.0), now_frac=now_frac)
            wet = [hours[k] for k, v in enumerate(mm) if (v or 0) >= 0.1]
            if wet:
                self.summary.set_label(
                    f"{u.precip(total)} of precipitation expected, mostly between "
                    f"{text.fmt_hour(wet[0], u)} and {text.fmt_hour(wet[-1], u)}.")
            else:
                self.summary.set_label("No precipitation expected.")
            facts = [("Total", u.precip(total)), ("Max chance", f"{round(maxp)}%"),
                     ("Wettest hour", u.precip(max([v or 0 for v in mm], default=0)))]

        elif m == "wind":
            spd = hv("wind_speed_10m", u.wind_value)
            gst = hv("wind_gusts_10m", u.wind_value)
            dirs = hv("wind_direction_10m")
            mx, mg = w.d("wind_speed_10m_max", d), w.d("wind_gusts_10m_max", d)
            dom = w.d("wind_direction_10m_dominant", d)
            self.headline.set_label(u.wind(mx))
            self.subhead.set_label(f"Max wind · gusts up to {u.wind(mg)}")
            self.chart.set_data(hours, [
                {"values": spd, "color": TEAL, "label": "Wind"},
                {"values": gst, "style": "dash", "color": GREY, "label": "Gusts", "fill": False},
            ], y_fmt=lambda v: f"{round(v)}", y_min=0,
                hover_fmt=hfmt(lambda i: f"{round(spd[i])} {u.wind_label()} {text.wind_direction_name(dirs[i])}"
                               f" · gusts {round(gst[i])}"), now_frac=now_frac)
            _, bname = text.beaufort(mx or 0)
            self.summary.set_label(
                f"Wind mostly from the {text.wind_direction_name(dom)}, peaking at {u.wind(mx)} "
                f"({bname.lower()}) with gusts up to {u.wind(mg)}.")
            facts = [("Max wind", u.wind(mx)), ("Max gusts", u.wind(mg)),
                     ("Direction", f"{text.wind_direction_name(dom)} ({round(dom or 0)}°)")]

        elif m == "humidity":
            hum = hv("relative_humidity_2m")
            dew = hv("dew_point_2m")
            valid = [v for v in hum if v is not None]
            avg = sum(valid) / len(valid) if valid else 0
            self.headline.set_label(f"{round(avg)}%")
            self.subhead.set_label("Average relative humidity")
            self.chart.set_data(hours, [{"values": hum, "color": TEAL, "label": "Humidity"}],
                                y_fmt=lambda v: f"{round(v)}%", y_min=0, y_max=100,
                                hover_fmt=hfmt(lambda i: f"{round(hum[i])}% · dew point {u.temp(dew[i])}"),
                                now_frac=now_frac)
            dvalid = [v for v in dew if v is not None]
            if dvalid:
                self.summary.set_label(
                    f"Humidity averages {round(avg)}% with a dew point from {u.temp(min(dvalid))} to "
                    f"{u.temp(max(dvalid))}.")
            facts = [("Average", f"{round(avg)}%"), ("Max", f"{round(max(valid, default=0))}%"),
                     ("Min", f"{round(min(valid, default=0))}%")]

        elif m == "uv":
            uv = hv("uv_index")
            mx = w.d("uv_index_max", d, 0)
            self.headline.set_label(f"{round(mx)}")
            self.subhead.set_label(f"Max UV index · {text.uv_level(mx)}")
            self.chart.set_data(hours, [{"values": uv, "color": (1.0, 0.75, 0.25), "label": "UV index"}],
                                y_fmt=lambda v: f"{round(v)}", y_min=0, y_max=11,
                                hover_fmt=hfmt(lambda i: f"{round(uv[i] or 0)} {text.uv_level(uv[i] or 0)}"),
                                now_frac=now_frac)
            high = [hours[k] for k, v in enumerate(uv) if (v or 0) >= 3]
            if high:
                self.summary.set_label(
                    f"UV is moderate or higher from {text.fmt_hour(high[0], u)} to "
                    f"{text.fmt_hour(high[-1], u)}. Use sun protection during these hours.")
            else:
                self.summary.set_label("UV index stays low all day.")
            facts = [("Max", f"{round(mx)} ({text.uv_level(mx)})")]

        elif m == "visibility":
            vis = hv("visibility")
            conv = (lambda v: v / 1609.344) if u.distance_unit == "mi" else (lambda v: v / 1000)
            vals = [None if v is None else conv(v) for v in vis]
            valid = [v for v in vis if v is not None]
            self.headline.set_label(u.distance(min(valid)) if valid else "--")
            self.subhead.set_label("Lowest visibility")
            dist = "mi" if u.distance_unit == "mi" else "km"
            self.chart.set_data(hours, [{"values": vals, "color": VIOLET, "label": "Visibility"}],
                                y_fmt=lambda v: f"{v:g} {dist}", y_min=0,
                                hover_fmt=hfmt(lambda i: u.distance(vis[i])), now_frac=now_frac)
            self.summary.set_label(text.visibility_text(min(valid)) if valid else "")
            facts = [("Min", u.distance(min(valid, default=None))), ("Max", u.distance(max(valid, default=None)))]

        elif m == "pressure":
            pr = hv("pressure_msl")
            vals = [None if v is None else u.pressure_value(v) for v in pr]
            valid = [v for v in pr if v is not None]
            self.headline.set_label(f"{u.pressure(valid[0]) if valid else '--'} {u.pressure_unit}")
            delta = (valid[-1] - valid[0]) if len(valid) > 1 else 0
            trend = "rising" if delta > 1 else "falling" if delta < -1 else "steady"
            self.subhead.set_label(f"Pressure is {trend} through the day")
            prec = 2 if u.pressure_unit == "inHg" else 0
            self.chart.set_data(hours, [{"values": vals, "color": BLUE, "label": "Pressure", "fill": False}],
                                y_fmt=lambda v: f"{v:.{prec}f}",
                                hover_fmt=hfmt(lambda i: f"{u.pressure(pr[i])} {u.pressure_unit}"), now_frac=now_frac)
            self.summary.set_label(
                f"Pressure ranges from {u.pressure(min(valid, default=None))} to "
                f"{u.pressure(max(valid, default=None))} {u.pressure_unit}. "
                "Falling pressure often signals unsettled weather; rising pressure, clearing skies.")
            facts = [("Min", u.pressure(min(valid, default=None))), ("Max", u.pressure(max(valid, default=None)))]

        elif m == "aqi":
            key = "us_aqi" if u.aqi == "us" else "european_aqi"
            ah = (w.air or {}).get("hourly") or {}
            times = ah.get("time") or []
            t0 = w.d("time", d)
            t1 = w.d("time", d + 1, t0 + 86400)
            sel = [k for k, t in enumerate(times) if t0 <= t < t1]
            vals = [(ah.get(key) or [None] * len(times))[k] for k in sel]
            ahours = [w.local(times[k]) for k in sel]
            valid = [v for v in vals if v is not None]
            if not valid:
                self.headline.set_label("--")
                self.subhead.set_label("No air quality forecast for this day")
                self.chart.set_data([], [])
                self.summary.set_label("")
            else:
                mx = max(valid)
                cat, desc = text.aqi_category(mx, u.aqi)
                self.headline.set_label(f"{round(mx)}")
                self.subhead.set_label(f"Peak {'US AQI' if u.aqi == 'us' else 'European AQI'} · {cat}")
                stops = drawing.US_AQI_STOPS if u.aqi == "us" else drawing.EU_AQI_STOPS
                color = drawing.color_at(stops, mx)
                anow = None
                if d == w.today_index() and len(sel) > 1:
                    anow = (w.now() - times[sel[0]]) / (times[sel[-1]] - times[sel[0]])
                self.chart.set_data(ahours, [{"values": vals, "color": color, "label": "AQI"}],
                                    y_fmt=lambda v: f"{round(v)}", y_min=0,
                                    hover_fmt=lambda i: f"{text.fmt_hour(ahours[i], u)} · {round(vals[i] or 0)} "
                                                        f"{text.aqi_category(vals[i], u.aqi)[0]}",
                                    now_frac=anow)
                self.summary.set_label(desc)
                facts = [("Peak", f"{round(mx)}"), ("Lowest", f"{round(min(valid))}")]

        for title, value in facts:
            self.facts.append(self._fact(title, value))
