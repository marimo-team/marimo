# Copyright 2024 Marimo. All rights reserved.
# Adapted from tornado.log (Apache 2.0 License)
from __future__ import annotations

import logging
import logging.handlers
import sys
from typing import Any, Dict, cast

try:
    import curses
except ImportError:
    curses = None  # type: ignore


def _stderr_supports_color() -> bool:
    try:
        if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
            if curses:
                curses.setupterm()  # type: ignore[attr-defined,unused-ignore] # noqa: E501
                if curses.tigetnum("colors") > 0:  # type: ignore[attr-defined,unused-ignore] # noqa: E501
                    return True
    except Exception:
        # Very broad exception handling because it's always better to
        # fall back to non-colored logs than to break at startup.
        pass
    return False


class LogFormatter(logging.Formatter):
    """Log formatter used in Tornado.

    Key features of this formatter are:

    * Color support when logging to a terminal that supports it.
    * Timestamps on every log line.
    * Robust against str/bytes encoding problems.

    Color support on Windows versions that do not support ANSI color codes is
    enabled by use of the colorama__ library. Applications that wish to use
    this must first initialize colorama with a call to ``colorama.init``.
    See the colorama documentation for details.

    __ https://pypi.python.org/pypi/colorama

    .. versionchanged:: 4.5
       Added support for ``colorama``. Changed the constructor
       signature to be compatible with `logging.config.dictConfig`.
    """

    DEFAULT_FORMAT = "%(color)s[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d]%(end_color)s %(message)s"  # noqa: E501
    DEFAULT_DATE_FORMAT = "%y%m%d %H:%M:%S"
    DEFAULT_COLORS = {
        logging.DEBUG: 4,  # Blue
        logging.INFO: 2,  # Green
        logging.WARNING: 3,  # Yellow
        logging.ERROR: 1,  # Red
        logging.CRITICAL: 5,  # Magenta
    }

    def __init__(
        self,
        fmt: str = DEFAULT_FORMAT,
        datefmt: str = DEFAULT_DATE_FORMAT,
        style: str = "%",
        color: bool = True,
        colors: Dict[int, int] = DEFAULT_COLORS,
    ) -> None:
        r"""
        :arg bool color: Enables color support.
        :arg str fmt: Log message format.
          It will be applied to the attributes dict of log records. The
          text between ``%(color)s`` and ``%(end_color)s`` will be colored
          depending on the level if color support is on.
        :arg dict colors: color mappings from logging level to terminal color
          code
        :arg str datefmt: Datetime format.
          Used for formatting ``(asctime)`` placeholder in ``prefix_fmt``.

        .. versionchanged:: 3.2

           Added ``fmt`` and ``datefmt`` arguments.
        """
        del style
        logging.Formatter.__init__(self, datefmt=datefmt)
        self._fmt = fmt

        self._colors = {}  # type: Dict[int, str]
        if color and _stderr_supports_color():
            if curses is not None:
                fg_color = (
                    curses.tigetstr("setaf") or curses.tigetstr("setf") or b""  # type: ignore[attr-defined,unused-ignore] # noqa: E501
                )

                for levelno, code in colors.items():
                    # Convert the terminal control characters from
                    # bytes to unicode strings for easier use with the
                    # logging module.
                    self._colors[levelno] = str(
                        curses.tparm(fg_color, code),
                        "ascii",  # type: ignore[attr-defined,unused-ignore] # noqa: E501
                    )
                normal = curses.tigetstr("sgr0")  # type: ignore[attr-defined,unused-ignore] # noqa: E501
                if normal is not None:
                    self._normal = str(normal, "ascii")
                else:
                    self._normal = ""
            else:
                # If curses is not present (currently we'll only get here for
                # colorama on windows), assume hard-coded ANSI color codes.
                for levelno, code in colors.items():
                    self._colors[levelno] = "\033[2;3%dm" % code
                self._normal = "\033[0m"
        else:
            self._normal = ""

    def format(self, record: Any) -> str | Any:
        try:
            message = record.getMessage()
            assert isinstance(message, str)  # guaranteed by logging
            record.message = message
        except Exception as e:
            record.message = "Bad message (%r): %r" % (e, record.__dict__)

        record.asctime = self.formatTime(record, cast(str, self.datefmt))

        if record.levelno in self._colors:
            record.color = self._colors[record.levelno]
            record.end_color = self._normal
        else:
            record.color = record.end_color = ""

        formatted = self._fmt % record.__dict__

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            # exc_text contains multiple lines.  We need to _safe_unicode
            # each line separately so that non-utf8 bytes don't cause
            # all the newlines to turn into '\n'.
            lines = [formatted.rstrip()]
            lines.extend(str(ln) for ln in record.exc_text.split("\n"))
            formatted = "\n".join(lines)
        return formatted.replace("\n", "\n    ")
