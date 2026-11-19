"""Logging setup: stderr (ends up in the journal when launched from GNOME) plus a rotating file."""

import logging
import logging.handlers
import os
from pathlib import Path
import sys
import threading

LOG_DIR = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "wxgtk"
LOG_FILE = LOG_DIR / "wxgtk.log"

log = logging.getLogger("wxgtk")
_configured = False


def setup(level=logging.INFO):
    global _configured
    if _configured:
        return
    _configured = True
    log.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    err = logging.StreamHandler(sys.stderr)
    err.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    log.addHandler(err)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=3,
                                                  encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    except OSError as e:
        log.warning("Can't open log file %s: %s", LOG_FILE, e)

    def excepthook(tp, val, tb):
        log.critical("Uncaught exception", exc_info=(tp, val, tb))

    def thread_excepthook(args):
        if args.exc_type is not SystemExit:
            log.critical("Uncaught exception in thread %s", getattr(args.thread, "name", "?"),
                         exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook
