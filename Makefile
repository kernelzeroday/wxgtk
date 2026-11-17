PREFIX ?= $(HOME)/.local
PY ?= /usr/bin/python3

.PHONY: run test install uninstall

run:
	$(PY) -m wxgtk

test:
	$(PY) -m unittest discover tests

install:
	install -d $(PREFIX)/share/wxgtk/wxgtk $(PREFIX)/bin $(PREFIX)/share/applications
	install -m644 wxgtk/*.py wxgtk/style.css $(PREFIX)/share/wxgtk/wxgtk/
	install -m755 bin/wxgtk $(PREFIX)/share/wxgtk/wxgtk-launcher
	ln -sf $(PREFIX)/share/wxgtk/wxgtk-launcher $(PREFIX)/bin/wxgtk
	install -m644 data/io.github.wxgtk.Weather.desktop $(PREFIX)/share/applications/

uninstall:
	rm -rf $(PREFIX)/share/wxgtk $(PREFIX)/bin/wxgtk $(PREFIX)/share/applications/io.github.wxgtk.Weather.desktop

VERSION := $(shell sed -n 's/^VERSION = "\(.*\)"/\1/p' wxgtk/__init__.py)
RPMTOP := $(CURDIR)/build/rpm

.PHONY: rpm
rpm:
	mkdir -p $(RPMTOP)/SOURCES
	git archive --format=tar.gz --prefix=wxgtk-$(VERSION)/ -o $(RPMTOP)/SOURCES/wxgtk-$(VERSION).tar.gz HEAD
	rpmbuild -ba --define "_topdir $(RPMTOP)" packaging/wxgtk.spec
	@find $(RPMTOP)/RPMS $(RPMTOP)/SRPMS -name '*.rpm'
