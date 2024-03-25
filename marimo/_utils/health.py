# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys
from typing import Optional


# Stub for missing modules
class _DefaultModule:
    __version__ = "missing"


def get_node_version() -> Optional[str]:
    try:
        process = subprocess.Popen(
            ["node", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        if stderr:
            return None
        return stdout.strip().split()[-1]
    except FileNotFoundError:
        return None


def get_required_modules_list() -> dict[str, str]:
    allowlist = [
        "click",
        "importlib_resources",
        "jedi",
        "markdown",
        "pymdown-extensions",
        "pygments",
        "tomlkit",
        "uvicorn",
        "starlette",
        "websocket",
        "typing_extensions",
        "black",
    ]
    # Consider listing all installed modules and their versions
    # Submodules and private modules are can be filtered with:
    #  if not ("." in m or m.startswith("_")):
    return {
        module: getattr(
            sys.modules.get(module, _DefaultModule), "__version__", "--"
        )
        for module in allowlist
    }


def get_chrome_version() -> Optional[str]:
    def get_chrome_version_windows() -> Optional[str]:
        process = subprocess.Popen(
            [
                "reg",
                "query",
                "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon",
                "/v",
                "version",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        if stderr:
            return None
        return stdout.strip().split()[-1]

    def get_chrome_version_mac() -> Optional[str]:
        process = subprocess.Popen(
            [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "--version",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        if stderr:
            return None
        return stdout.strip().split()[-1]

    def get_chrome_version_linux() -> Optional[str]:
        process = subprocess.Popen(
            ["google-chrome", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        if stderr:
            return None
        return stdout.strip().split()[-1]

    try:
        if sys.platform.startswith("win32"):
            return get_chrome_version_windows()
        elif sys.platform.startswith("darwin"):
            return get_chrome_version_mac()
        elif sys.platform.startswith("linux"):
            return get_chrome_version_linux()
        else:
            return None
    except FileNotFoundError:
        return None
