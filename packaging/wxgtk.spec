Name:           wxgtk
Version:        0.1.0
Release:        1%{?dist}
Summary:        GTK4 weather app with forecasts, conditions and air quality
License:        LicenseRef-Unspecified
URL:            https://github.com/kernelzeroday/wxgtk
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3
BuildRequires:  desktop-file-utils

Requires:       python3
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk4 >= 4.10
Requires:       libadwaita >= 1.6
Requires:       adwaita-icon-theme
Recommends:     geoclue2-libs

%description
A GTK4 and libadwaita weather app modeled on Apple Weather's feature set:
saved locations, animated condition-aware sky, hourly and 10-day forecasts,
next-hour precipitation, air quality, detail tiles (UV, sun, wind, pressure,
moon phase, etc.) and interactive per-day charts. Data from Open-Meteo.

%prep
%autosetup

%build
# pure Python, nothing to build

%install
install -d %{buildroot}%{_datadir}/%{name}/wxgtk %{buildroot}%{_bindir}
install -m644 wxgtk/*.py wxgtk/style.css %{buildroot}%{_datadir}/%{name}/wxgtk/
install -m755 bin/wxgtk %{buildroot}%{_datadir}/%{name}/wxgtk-launcher
ln -s ../share/%{name}/wxgtk-launcher %{buildroot}%{_bindir}/wxgtk
desktop-file-install --dir=%{buildroot}%{_datadir}/applications data/io.github.wxgtk.Weather.desktop

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.wxgtk.Weather.desktop
PYTHONDONTWRITEBYTECODE=1 %{__python3} -m unittest discover tests

%files
%doc README.md
%{_bindir}/wxgtk
%{_datadir}/%{name}/
%{_datadir}/applications/io.github.wxgtk.Weather.desktop

%changelog
* Tue Nov 17 2026 kelsey <11334159+kernelzeroday@users.noreply.github.com> - 0.1.0-1
- Initial package
