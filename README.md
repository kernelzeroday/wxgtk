# wxgtk — Weather for GTK4

A GTK4 + libadwaita weather app modeled on Apple Weather's feature set. Data comes from
[Open-Meteo](https://open-meteo.com), which is free and needs no API key.

## Features

- **Locations sidebar.** Saved cities show local time, condition, temperature and high/low.
  Search, preview a result before adding it, reorder or remove (right-click or long-press,
  `Delete`, undo toast), and use your current location via GeoClue.
- **Hero.** Location, current temperature, condition, and today's high/low.
- **Animated sky.** The gradient follows condition and day/night, with rain, snow, lightning,
  drifting clouds and twinkling stars. It respects the system "reduce animations" setting.
- **Next-hour precipitation.** Shown only when rain or snow is coming: 15-minute
  intensity bars and a "Rain starting in ~25 min" headline.
- **Hourly forecast.** The next 24 hours, with sunrise/sunset markers, precipitation chance,
  and a summary line ("Rainy conditions expected around 3 PM. Wind gusts up to 40 km/h.").
- **10-day forecast.** Temperature range bars colored by temperature, with a current-temperature dot.
- **Air quality.** US AQI or European AQI with a category, health advice and pollutants.
- **Tiles.** UV index, sunrise/sunset arc, wind compass and gusts, precipitation (last 24h and
  next expected), feels-like with an explanation, humidity and dew point, visibility, a pressure
  gauge with trend, and moon phase with illumination.
- **Conditions dialog.** Click any card or day to see interactive hourly charts per day
  (hover shows values) for temperature/feels-like, precipitation, wind/gusts, humidity, UV,
  visibility, pressure and AQI, with a daily summary.
- **Units.** °C/°F, km/h, m/s, mph, kn, mm/in, hPa/inHg/mmHg, km/mi, and 12/24-hour time.
  Defaults come from the locale.
- **Offline start.** The last forecast is cached and shown right away. Data refreshes
  every 10 minutes.
- **Adaptive layout.** Two columns when wide, and a collapsing sidebar on phone-sized windows.

## Requirements

Fedora: `sudo dnf install python3-gobject gtk4 libadwaita geoclue2-libs`
(GTK ≥ 4.10, libadwaita ≥ 1.6). Use the **system** Python (`/usr/bin/python3`), because PyGObject
comes from the distribution.

## Install (RPM)

```sh
make rpm
sudo dnf install build/rpm/RPMS/noarch/wxgtk-*.noarch.rpm
```

Prebuilt RPMs are attached to [GitHub releases](https://github.com/kernelzeroday/wxgtk/releases).

## Run from source

```sh
make run          # or: /usr/bin/python3 -m wxgtk
make test
make install      # into ~/.local (PREFIX=... to change)
```

## Shortcuts

`Ctrl+F` search · `Ctrl+R`/`F5` refresh · `Ctrl+M` my location · `Delete` remove location ·
`Ctrl+,` preferences · `Ctrl+?` shortcuts · `Ctrl+Q` quit

## Not (yet) implemented vs. Apple Weather

- Precipitation/temperature radar **maps**. These would need libshumate plus a tile source.
- Severe weather **alerts**. Open-Meteo doesn't provide them; NWS or MeteoAlarm could be added per region.
- Historical **averages** comparisons. The Open-Meteo archive/climate API could provide them.
- Notifications.

Config: `~/.config/wxgtk/config.json` · cache: `~/.cache/wxgtk/`
