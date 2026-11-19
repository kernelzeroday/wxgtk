"""Main window: location sidebar + weather content."""

import logging
import threading
import time

from gi.repository import Adw, Gdk, GLib, Gtk

from . import api, codes, config as cfg, geoloc, text
from .detail import DetailDialog
from .drawing import SkyBackground, sky_wind
from .model import Weather
from .prefs import PreferencesDialog
from .view import WeatherView, clear, label

log = logging.getLogger(__name__)

REFRESH_SECONDS = 10 * 60


class WeatherWindow(Adw.ApplicationWindow):
    def __init__(self, app, config):
        super().__init__(application=app, title="Weather", default_width=1180, default_height=840)
        self.set_size_request(360, 480)
        self.config = config
        self.weathers: dict[str, Weather] = {}
        self.errors: dict[str, str] = {}
        self.loading: set[str] = set()
        self.current: api.Location | None = None
        self.previewing = False
        self._search_serial = 0
        self._suppress_select = False
        self._rendered_hour = None

        self.toasts = Adw.ToastOverlay()
        self.split = Adw.NavigationSplitView(min_sidebar_width=270, max_sidebar_width=340)
        self.split.set_sidebar(Adw.NavigationPage(title="Weather", child=self._build_sidebar()))
        self.content_page = Adw.NavigationPage(title="Weather", child=self._build_content())
        self.split.set_content(self.content_page)
        self.toasts.set_child(self.split)
        self.set_content(self.toasts)

        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 680sp"))
        bp.add_setter(self.split, "collapsed", True)
        self.add_breakpoint(bp)

        self._install_shortcuts()

        # restore cached data so the UI is immediately useful, then refresh
        for loc in self.config.locations:
            raw = cfg.load_cache(loc.id)
            if raw:
                try:
                    self.weathers[loc.id] = Weather(raw)
                except (KeyError, TypeError):
                    pass
        self._rebuild_saved()
        if self.config.locations:
            sel = min(max(self.config.selected, 0), len(self.config.locations) - 1)
            self._select_index(sel)
        else:
            self.render()
        self.refresh_all()
        if self.config.use_current_location:
            self.locate()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._on_refresh_timer)
        GLib.timeout_add_seconds(30, self._on_clock_tick)

    # ==================================================================
    # construction
    # ==================================================================
    def _build_sidebar(self):
        tv = Adw.ToolbarView()
        header = Adw.HeaderBar()
        menu = Gtk.PopoverMenu.new_from_model(self._app_menu())
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", popover=menu, tooltip_text="Main Menu")
        menu_btn.set_primary(True)
        header.pack_end(menu_btn)
        locate_btn = Gtk.Button(icon_name="find-location-symbolic", tooltip_text="Use My Location")
        locate_btn.set_action_name("win.locate")
        header.pack_start(locate_btn)
        tv.add_top_bar(header)

        self.search = Gtk.SearchEntry(placeholder_text="Search for a city or airport", search_delay=350)
        self.search.set_margin_start(10)
        self.search.set_margin_end(10)
        self.search.set_margin_bottom(6)
        self.search.connect("search-changed", self._on_search_changed)
        self.search.connect("activate", self._on_search_activate)
        self.search.connect("stop-search", lambda e: e.set_text(""))
        self.search.set_key_capture_widget(self)
        tv.add_top_bar(self.search)

        self.saved_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.saved_list.add_css_class("navigation-sidebar")
        self.saved_list.connect("row-selected", self._on_saved_selected)
        self.saved_list.connect("row-activated", lambda *_: self.split.set_show_content(True))
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_saved_key)
        self.saved_list.add_controller(keys)

        self.results_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.results_list.add_css_class("navigation-sidebar")
        self.results_list.connect("row-activated", lambda _l, row: self.preview(row.loc))

        empty = Adw.StatusPage(icon_name="find-location-symbolic", title="No Locations",
                               description="Search for a city above, or use your current location.")
        empty.add_css_class("compact")
        btn = Gtk.Button(label="Use My Location", halign=Gtk.Align.CENTER, action_name="win.locate")
        btn.add_css_class("pill")
        btn.add_css_class("suggested-action")
        empty.set_child(btn)

        self.results_status = Adw.StatusPage(icon_name="edit-find-symbolic", title="Searching…")
        self.results_status.add_css_class("compact")

        self.side_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.side_stack.add_named(Gtk.ScrolledWindow(child=self.saved_list, vexpand=True), "saved")
        self.side_stack.add_named(empty, "empty")
        self.side_stack.add_named(Gtk.ScrolledWindow(child=self.results_list, vexpand=True), "results")
        self.side_stack.add_named(self.results_status, "results-status")
        tv.set_content(self.side_stack)
        return tv

    def _app_menu(self):
        from gi.repository import Gio
        menu = Gio.Menu()
        sec = Gio.Menu()
        sec.append("Refresh", "win.refresh")
        sec.append("Use My Location", "win.locate")
        menu.append_section(None, sec)
        sec2 = Gio.Menu()
        sec2.append("Preferences", "app.preferences")
        sec2.append("Keyboard Shortcuts", "win.show-help-overlay")
        sec2.append("About Weather", "app.about")
        menu.append_section(None, sec2)
        return menu

    def _build_content(self):
        tv = Adw.ToolbarView(extend_content_to_top_edge=True)
        tv.set_top_bar_style(Adw.ToolbarStyle.FLAT)
        header = Adw.HeaderBar()
        header.add_css_class("wx-header")
        self.title = Adw.WindowTitle(title="", subtitle="")
        header.set_title_widget(self.title)
        self.refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh (Ctrl+R)")
        self.refresh_btn.set_action_name("win.refresh")
        self.refresh_spinner = Adw.Spinner()
        self.refresh_stack = Gtk.Stack()
        self.refresh_stack.add_named(self.refresh_btn, "button")
        self.refresh_stack.add_named(self.refresh_spinner, "spinner")
        header.pack_end(self.refresh_stack)
        self.add_btn = Gtk.Button(label="Add", visible=False)
        self.add_btn.add_css_class("suggested-action")
        self.add_btn.connect("clicked", lambda *_: self.add_preview())
        header.pack_end(self.add_btn)
        self.cancel_btn = Gtk.Button(label="Cancel", visible=False)
        self.cancel_btn.connect("clicked", lambda *_: self.cancel_preview())
        header.pack_start(self.cancel_btn)
        tv.add_top_bar(header)

        self.sky = SkyBackground()
        self.view = WeatherView(self.open_detail)
        clamp = Adw.Clamp(maximum_size=1060, tightening_threshold=700, child=self.view)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, child=clamp)
        bin_ = Adw.BreakpointBin(child=self.scroller)
        bin_.set_size_request(320, 300)
        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 780sp"))
        narrow.connect("apply", lambda *_: self.view.set_narrow(True))
        narrow.connect("unapply", lambda *_: self.view.set_narrow(False))
        bin_.add_breakpoint(narrow)

        self.loading_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                                    valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        sp = Adw.Spinner()
        sp.set_size_request(48, 48)
        self.loading_page.append(sp)
        self.loading_label = label("Loading forecast…", "weather-view", xalign=0.5)
        self.loading_page.append(self.loading_label)

        self.error_page = Adw.StatusPage(icon_name="network-offline-symbolic", title="Couldn't Load Weather")
        retry = Gtk.Button(label="Try Again", halign=Gtk.Align.CENTER, action_name="win.refresh")
        retry.add_css_class("pill")
        self.error_page.set_child(retry)

        self.welcome_page = Adw.StatusPage(icon_name="weather-few-clouds-symbolic", title="Weather",
                                           description="Search for a place to see its forecast.")

        self.content_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.add_css_class("weather-view")
        self.content_stack.add_named(bin_, "weather")
        self.content_stack.add_named(self.loading_page, "loading")
        self.content_stack.add_named(self.error_page, "error")
        self.content_stack.add_named(self.welcome_page, "welcome")

        overlay = Gtk.Overlay(child=self.sky)
        overlay.add_overlay(self.content_stack)
        tv.set_content(overlay)
        tv.add_css_class("wx-content")
        return tv

    def _install_shortcuts(self):
        from gi.repository import Gio
        for name, cb in (("refresh", lambda *_: self.refresh_all(force=True)),
                         ("locate", lambda *_: self.locate()),
                         ("search", lambda *_: self._focus_search()),
                         ("remove-location", lambda *_: self._remove_selected())):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            self.add_action(act)
        app = self.get_application()
        app.set_accels_for_action("win.refresh", ["<Ctrl>r", "F5"])
        app.set_accels_for_action("win.search", ["<Ctrl>f", "<Ctrl>l"])
        app.set_accels_for_action("win.locate", ["<Ctrl>m"])
        self._build_help_overlay()

    def _build_help_overlay(self):
        dialog = Adw.ShortcutsDialog()
        sec = Adw.ShortcutsSection(title="General")
        for title, accel in (("Search Locations", "<Ctrl>f"), ("Refresh", "<Ctrl>r"),
                             ("Use My Location", "<Ctrl>m"), ("Remove Selected Location", "Delete"),
                             ("Preferences", "<Ctrl>comma"), ("Keyboard Shortcuts", "<Ctrl>question"),
                             ("Quit", "<Ctrl>q")):
            sec.add(Adw.ShortcutsItem(title=title, accelerator=accel))
        dialog.add(sec)
        self._shortcuts_dialog = dialog
        from gi.repository import Gio
        act = Gio.SimpleAction.new("show-help-overlay", None)
        act.connect("activate", lambda *_: self._shortcuts_dialog.present(self))
        self.add_action(act)
        self.get_application().set_accels_for_action("win.show-help-overlay", ["<Ctrl>question"])

    # ==================================================================
    # sidebar
    # ==================================================================
    def _focus_search(self):
        self.split.set_show_content(False)
        self.search.grab_focus()

    def _saved_row(self, loc):
        row = Gtk.ListBoxRow()
        row.loc = loc
        grid = Gtk.Grid(column_spacing=8, row_spacing=2)
        grid.set_margin_top(6)
        grid.set_margin_bottom(6)
        grid.set_margin_start(4)
        grid.set_margin_end(4)
        w = self.weathers.get(loc.id)
        name = Gtk.Box(spacing=4, hexpand=True)
        if loc.is_current:
            img = Gtk.Image.new_from_icon_name("find-location-symbolic")
            img.set_pixel_size(12)
            name.append(img)
        name.append(label(loc.name, "heading", ellipsize=True))
        grid.attach(name, 0, 0, 1, 1)
        if w:
            sub = text.fmt_time(w.local(time.time()), self.config.units)
            if loc.is_current:
                sub = f"My Location · {sub}"
            temp = self.config.units.temp(w.c("temperature_2m"))
            d0 = w.today_index()
            cond = codes.describe(w.c("weather_code"))
            hilo = (f"H:{self.config.units.temp(w.d('temperature_2m_max', d0))} "
                    f"L:{self.config.units.temp(w.d('temperature_2m_min', d0))}")
            icon = codes.icon(w.c("weather_code"), w.is_day)
        else:
            sub = loc.subtitle
            temp, cond, hilo, icon = "--", "Loading…" if loc.id in self.loading else "", "", None
        grid.attach(label(sub, "caption", "dim", ellipsize=True), 0, 1, 1, 1)
        tbox = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        if icon:
            img = Gtk.Image.new_from_icon_name(icon)
            img.set_pixel_size(20)
            tbox.append(img)
        tbox.append(label(temp, "side-temp", xalign=1))
        grid.attach(tbox, 1, 0, 1, 2)
        grid.attach(label(cond, "caption", ellipsize=True), 0, 2, 1, 1)
        grid.attach(label(hilo, "caption", xalign=1), 1, 2, 1, 1)
        row.set_child(grid)
        row.set_tooltip_text(", ".join(p for p in (loc.name, loc.region, loc.country) if p))

        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", lambda _g, _n, x, y: self._row_menu(row, x, y))
        row.add_controller(click)
        press = Gtk.GestureLongPress()
        press.connect("pressed", lambda _g, x, y: self._row_menu(row, x, y))
        row.add_controller(press)
        return row

    def _row_menu(self, row, x, y):
        idx = self.config.locations.index(row.loc) if row.loc in self.config.locations else -1
        if idx < 0:
            return
        pop = Gtk.Popover(has_arrow=True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for title, cb, sensitive in (
            ("Move Up", lambda: self._move(idx, -1), idx > 0),
            ("Move Down", lambda: self._move(idx, 1), idx < len(self.config.locations) - 1),
            ("Remove", lambda: self._remove(idx), True),
        ):
            b = Gtk.Button(label=title, sensitive=sensitive)
            b.add_css_class("flat")
            b.get_child().set_xalign(0)

            def on_click(_b, cb=cb):
                pop.popdown()
                GLib.idle_add(lambda: (cb(), False)[1])
            b.connect("clicked", on_click)
            box.append(b)
        pop.set_child(box)
        pop.set_parent(row)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        pop.set_pointing_to(rect)
        pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1]))
        pop.popup()

    def _move(self, idx, delta):
        locs = self.config.locations
        j = idx + delta
        if 0 <= j < len(locs):
            locs[idx], locs[j] = locs[j], locs[idx]
            sel = self._selected_index()
            self.config.save()
            self._rebuild_saved()
            if sel == idx:
                self._select_index(j)
            elif sel == j:
                self._select_index(idx)
            elif sel is not None:
                self._select_index(sel)

    def _remove(self, idx):
        locs = self.config.locations
        if not (0 <= idx < len(locs)):
            return
        loc = locs.pop(idx)
        if loc.is_current:
            self.config.use_current_location = False
        self.config.save()
        was_current = self.current is not None and self.current.id == loc.id and not self.previewing
        self._rebuild_saved()
        if was_current:
            if locs:
                self._select_index(min(idx, len(locs) - 1))
            else:
                self.current = None
                self.render()
        toast = Adw.Toast(title=f"Removed {loc.name}", button_label="Undo", timeout=5)
        toast.connect("button-clicked", lambda *_: self._undo_remove(idx, loc))
        self.toasts.add_toast(toast)

    def _undo_remove(self, idx, loc):
        self.config.locations.insert(min(idx, len(self.config.locations)), loc)
        if loc.is_current:
            self.config.use_current_location = True
        self.config.save()
        self._rebuild_saved()
        self._select_index(self.config.locations.index(loc))

    def _remove_selected(self):
        idx = self._selected_index()
        if idx is not None:
            self._remove(idx)

    def _on_saved_key(self, _ctl, keyval, _code, _state):
        if keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete):
            self._remove_selected()
            return True
        return False

    def _selected_index(self):
        row = self.saved_list.get_selected_row()
        return row.get_index() if row else None

    def _select_index(self, idx):
        row = self.saved_list.get_row_at_index(idx)
        if row:
            self.saved_list.select_row(row)

    def _rebuild_saved(self):
        sel = self._selected_index()
        sel_id = self.current.id if (self.current and not self.previewing) else None
        self._suppress_select = True
        clear(self.saved_list)
        target = None
        for i, loc in enumerate(self.config.locations):
            row = self._saved_row(loc)
            self.saved_list.append(row)
            if loc.id == sel_id:
                target = row
        if target is not None:
            self.saved_list.select_row(target)
        elif sel is not None and not self.previewing:
            self._select_index(min(sel, len(self.config.locations) - 1))
        self._suppress_select = False
        if not self.search.get_text():
            self.side_stack.set_visible_child_name("saved" if self.config.locations else "empty")

    def _on_saved_selected(self, _lb, row):
        if self._suppress_select or row is None:
            return
        self.previewing = False
        self.current = row.loc
        self.config.selected = row.get_index()
        self.config.save()
        self.render()
        if row.loc.id not in self.weathers or self._stale(row.loc.id):
            self.fetch(row.loc)

    # ---- search ------------------------------------------------------
    def _on_search_changed(self, entry):
        q = entry.get_text().strip()
        self._search_serial += 1
        serial = self._search_serial
        if not q:
            self.side_stack.set_visible_child_name("saved" if self.config.locations else "empty")
            return
        self.results_status.set_title("Searching…")
        self.results_status.set_description(None)
        self.side_stack.set_visible_child_name("results-status")

        def work():
            try:
                res, err = api.search_locations(q), None
            except api.ApiError as e:
                log.warning("Location search for %r failed: %s", q, e)
                res, err = [], str(e)
            GLib.idle_add(self._on_search_results, serial, res, err)

        threading.Thread(target=work, daemon=True).start()

    def _on_search_results(self, serial, results, err):
        if serial != self._search_serial or not self.search.get_text().strip():
            return False
        clear(self.results_list)
        if err or not results:
            self.results_status.set_title("Search Failed" if err else "No Results")
            self.results_status.set_description(err or "Try a different spelling or a nearby city.")
            self.side_stack.set_visible_child_name("results-status")
            return False
        for loc in results:
            row = Adw.ActionRow(title=loc.name, subtitle=loc.subtitle, activatable=True)
            row.loc = loc
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            self.results_list.append(row)
        self.side_stack.set_visible_child_name("results")
        return False

    def _on_search_activate(self, _entry):
        row = self.results_list.get_row_at_index(0)
        if row is not None and self.side_stack.get_visible_child_name() == "results":
            self.preview(row.loc)

    def preview(self, loc):
        for i, saved in enumerate(self.config.locations):
            if saved.id == loc.id:
                self.search.set_text("")
                self._select_index(i)
                self.split.set_show_content(True)
                return
        self.previewing = True
        self.current = loc
        self.saved_list.unselect_all()
        self.render()
        self.split.set_show_content(True)
        self.fetch(loc)

    def add_preview(self):
        if not self.previewing or self.current is None:
            return
        loc = self.current
        self.config.locations.append(loc)
        self.previewing = False
        self.config.save()
        if loc.id in self.weathers:
            cfg.save_cache(loc.id, self.weathers[loc.id].raw)
        self.search.set_text("")
        self._rebuild_saved()
        self._select_index(len(self.config.locations) - 1)
        self.toasts.add_toast(Adw.Toast(title=f"Added {loc.name}", timeout=2))

    def cancel_preview(self):
        self.previewing = False
        self.current = None
        if self.config.locations:
            idx = min(max(self.config.selected, 0), len(self.config.locations) - 1)
            row = self.saved_list.get_row_at_index(idx)
            self.saved_list.unselect_all()
            if row:
                self.saved_list.select_row(row)
        else:
            self.render()
        self.split.set_show_content(False)

    # ==================================================================
    # data
    # ==================================================================
    def _stale(self, loc_id):
        w = self.weathers.get(loc_id)
        return w is None or time.time() - w.fetched > REFRESH_SECONDS

    def fetch(self, loc):
        if loc.id in self.loading:
            return
        self.loading.add(loc.id)
        self._update_busy()

        def work():
            try:
                raw, err = api.fetch_weather(loc.lat, loc.lon), None
            except api.ApiError as e:
                raw, err = None, str(e)
            except Exception as e:  # unexpected parse failure etc.
                log.exception("Unexpected error fetching weather for %s", loc.name)
                raw, err = None, f"Unexpected error: {e}"
            GLib.idle_add(self._on_fetched, loc, raw, err)

        threading.Thread(target=work, daemon=True).start()

    def _on_fetched(self, loc, raw, err):
        self.loading.discard(loc.id)
        self._update_busy()
        is_shown = self.current is not None and self.current.id == loc.id
        if raw is not None:
            try:
                self.weathers[loc.id] = Weather(raw)
            except (KeyError, TypeError) as e:
                log.exception("Malformed weather response for %s", loc.name)
                raw, err = None, f"Malformed response: {e}"
        if raw is not None:
            if loc.id in self.errors:
                log.info("Weather for %s recovered", loc.name)
            self.errors.pop(loc.id, None)
            if any(l.id == loc.id for l in self.config.locations):
                cfg.save_cache(loc.id, raw)
        else:
            self.errors[loc.id] = err
            log.error("Weather update failed for %s (%s): %s", loc.name, loc.id, err)
            if is_shown and loc.id in self.weathers:
                self.toasts.add_toast(Adw.Toast(title=f"Couldn't update: {err}", timeout=4))
        self._rebuild_saved()
        if is_shown:
            self.render(keep_scroll=True)
        return False

    def refresh_all(self, force=False):
        for loc in self.config.locations:
            if force or self._stale(loc.id):
                self.fetch(loc)
        if self.previewing and self.current is not None:
            self.fetch(self.current)

    def _on_refresh_timer(self):
        self.refresh_all()
        return GLib.SOURCE_CONTINUE

    def _on_clock_tick(self):
        self._rebuild_saved()
        if self.current and self.current.id in self.weathers:
            w = self.weathers[self.current.id]
            if w.hour_index() != self._rendered_hour:
                self.render(keep_scroll=True)
        return GLib.SOURCE_CONTINUE

    def _update_busy(self):
        busy = self.current is not None and self.current.id in self.loading
        self.refresh_stack.set_visible_child_name("spinner" if busy else "button")

    # ---- current location ---------------------------------------------
    def locate(self):
        self.toasts.add_toast(Adw.Toast(title="Finding your location…", timeout=2))
        geoloc.locate(self._on_located)

    def _on_located(self, lat, lon, err):
        if err:
            log.warning("Current location unavailable: %s", err)
            self.toasts.add_toast(Adw.Toast(title=f"Location unavailable: {err}", timeout=5))
            return

        def work():
            loc = api.reverse_geocode(lat, lon)
            GLib.idle_add(self._on_current_location, loc)

        threading.Thread(target=work, daemon=True).start()

    def _on_current_location(self, loc):
        locs = self.config.locations
        locs[:] = [l for l in locs if not l.is_current and l.id != loc.id]
        locs.insert(0, loc)
        self.config.use_current_location = True
        self.config.save()
        self.previewing = False
        self.search.set_text("")
        self._rebuild_saved()
        self._select_index(0)
        self.fetch(loc)
        return False

    # ==================================================================
    # rendering
    # ==================================================================
    def render(self, keep_scroll=False):
        loc = self.current
        self.add_btn.set_visible(self.previewing)
        self.cancel_btn.set_visible(self.previewing)
        self._update_busy()
        if loc is None:
            self.title.set_title("")
            self.title.set_subtitle("")
            self.content_page.set_title("Weather")
            self.sky.set_condition("clear", True)
            self.content_stack.set_visible_child_name("welcome")
            return
        self.content_page.set_title(loc.name)
        w = self.weathers.get(loc.id)
        if w is None:
            self.sky.set_condition("cloudy", True)
            self.title.set_title("")
            if loc.id in self.errors and loc.id not in self.loading:
                self.error_page.set_description(self.errors[loc.id])
                self.content_stack.set_visible_child_name("error")
            else:
                self.loading_label.set_label(f"Loading forecast for {loc.name}…")
                self.content_stack.set_visible_child_name("loading")
            return
        code = w.c("weather_code")
        self.sky.set_condition(codes.kind(code), w.is_day, intensity=codes.intensity(code),
                               variant=codes.variant(code),
                               wind=sky_wind(w.c("wind_speed_10m", 0), w.c("wind_direction_10m")))
        adj = self.scroller.get_vadjustment()
        pos = adj.get_value() if keep_scroll else 0
        self.view.update(loc, w, self.config.units)
        self._rendered_hour = w.hour_index()
        self.title.set_title("")
        self.content_stack.set_visible_child_name("weather")
        GLib.idle_add(lambda: (adj.set_value(pos), False)[1])

    def open_detail(self, metric, day):
        if self.current is None or self.current.id not in self.weathers:
            return
        DetailDialog(self.weathers[self.current.id], self.config.units, self.current.name,
                     metric=metric, day=day).present(self)

    def show_preferences(self):
        def changed():
            self._rebuild_saved()
            self.render(keep_scroll=True)
        PreferencesDialog(self.config, changed).present(self)
