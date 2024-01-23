# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import platform
import subprocess
import sys
from typing import Optional, Union

from marimo import __version__


def get_system_info() -> dict[str, Union[str, dict[str, str]]]:
    info = {
        "marimo": __version__,
        "OS": platform.system(),
        "OS Version": platform.release(),
        # e.g., x86 or arm
        "Processor": platform.processor(),
        "Python Version": platform.python_version(),
    }

    binaries = {
        "Chrome": _get_chrome_version() or "--",
        "Node": _get_node_version() or "--",
    }

    requirements = _get_pip_list()

    return {**info, "Binaries": binaries, "Requirements": requirements}


def _get_node_version() -> Optional[str]:
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


def _get_pip_list() -> dict[str, str]:
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
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "list",
                "--format=json",
                "--disable-pip-version-check",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        packages = json.loads(result.stdout)
        return {
            package["name"]: package["version"]
            for package in packages
            if package["name"] in allowlist
        }
    except FileNotFoundError:
        return {}


def _get_chrome_version() -> Optional[str]:
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
