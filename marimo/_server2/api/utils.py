from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from shutil import which
from typing import Optional


# TODO: test
def require_header(header: list[str] | None) -> str:
    """
    Require exactly one value in header and return it.
    """

    if header is None:
        raise ValueError("Expected exactly one value in header, got None")
    if len(header) != 1:
        raise ValueError(
            f"Expected exactly one value in header, got {len(header)} values: {header}"
        )
    return header[0]


# TODO: test
def parse_title(filename: Optional[str]) -> str:
    """
    Parse a filename into a (name, extension) tuple.
    """
    if filename is None:
        return "marimo"

    # filename is used as title, except basename and suffix are
    # stripped and underscores are replaced with spaces
    return os.path.splitext(os.path.basename(filename))[0].replace("_", " ")


def open_url_in_browser(browser: str, url: str) -> None:
    """
    Open a browser to the given URL.
    """
    if which("xdg-open") is not None and browser == "default":
        with open(os.devnull, "w") as devnull:
            if sys.platform == "win32" or sys.platform == "cygwin":
                preexec_fn = None
            else:
                preexec_fn = os.setpgrp
            subprocess.Popen(
                ["xdg-open", url],
                # don't forward signals: ctrl-c shouldn't kill the browser
                # TODO: test/workaround on windows
                preexec_fn=preexec_fn,
                stdout=devnull,
                stderr=subprocess.STDOUT,
            )
    else:
        if browser == "default":
            webbrowser.open(url)
        else:
            webbrowser.get(browser).open(url)
