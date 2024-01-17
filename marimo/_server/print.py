# Copyright 2024 Marimo. All rights reserved.
import os
import sys
from typing import Optional

from marimo._server.utils import print_tabbed

UTF8_SUPPORTED = False

try:
    "🌊🍃".encode(sys.stdout.encoding)
    UTF8_SUPPORTED = True
except Exception:
    pass


def print_startup(filename: Optional[str], url: str, run: bool) -> None:
    print()
    if filename is not None and not run:
        print_tabbed(
            f"\033[1;32mEdit {os.path.basename(filename)} "
            "in your browser\033[0m " + _utf8("📝")
        )
    elif filename is not None and run:
        print_tabbed(
            f"\033[1;32mRunning {os.path.basename(filename)}"
            "\033[0m " + _utf8("⚡")
        )
    else:
        print_tabbed(
            "\033[1;32mCreate a new marimo app in your browser\033[0m "
            + _utf8("🛠")
        )
    print()
    print_tabbed(f"\033[32mURL\033[0m: \033[1m{url}\033[0m")
    print()


def print_shutdown() -> None:
    print()
    print_tabbed("\033[32mThanks for using marimo!\033[0m %s" % _utf8("🌊🍃"))
    print()


def _utf8(msg: str) -> str:
    return msg if UTF8_SUPPORTED else ""
