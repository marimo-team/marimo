# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any, cast

from marimo import _loggers
from marimo._config.manager import get_default_config_manager
from marimo._utils.health import (
    get_chrome_version,
    get_node_version,
    get_optional_modules_list,
    get_required_modules_list,
    get_uv_version,
)
from marimo._utils.versions import is_editable
from marimo._version import __version__

LOGGER = _loggers.marimo_logger()


def is_win11() -> bool:
    """
    Check if the operating system is Windows 11.

    Returns:
        bool: True if the OS is Windows 11, False otherwise.
    """
    if hasattr(sys, "getwindowsversion"):
        return cast(Any, sys).getwindowsversion().build >= 22000  # type: ignore[no-any-return]
    return False


def get_experimental_flags() -> dict[str, str | bool | dict[str, Any]]:
    try:
        config = get_default_config_manager(current_path=None).get_config()
        experimental_config = config.get("experimental", {})
        return {
            k: v
            for k, v in experimental_config.items()
            if isinstance(v, (str, bool, dict))
        }
    except Exception:
        LOGGER.error("Failed to get experimental flags")
        return {}


def get_default_locale() -> str:
    try:
        import locale

        # getdefaultlocale is deprecated in 3.13+ and removed in 3.15
        # Use getlocale() with LC_ALL as a fallback chain
        loc = locale.getlocale(locale.LC_ALL)
        if loc[0]:
            return loc[0]
        # Try LC_MESSAGES on Unix-like systems
        try:
            loc = locale.getlocale(locale.LC_MESSAGES)
            if loc[0]:
                return loc[0]
        except AttributeError:
            pass
        # Fall back to environment variable check
        import os

        for env_var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
            val = os.environ.get(env_var)
            if val:
                # Extract locale name (e.g., "en_US" from "en_US.UTF-8")
                return val.split(".")[0]
        return "--"
    except Exception:
        return "--"


def abbreviate_home(path: str, *, home: Path | None = None) -> str:
    """
    Replace the user's home directory prefix in `path` with `~`.

    Paths outside the home directory are returned unchanged.

    Args:
        path (str): The path to abbreviate.
        home (Path, optional): The home directory to match against. Defaults to
            the current user's home directory.

    Returns:
        str: The path with the home prefix replaced by `~`, or unchanged.
    """
    home_path = (home or Path.home()).as_posix().rstrip("/")
    normalized = Path(path).as_posix()
    if normalized == home_path:
        return "~"
    if normalized.startswith(f"{home_path}/"):
        return f"~{normalized[len(home_path) :]}"
    return normalized


def get_system_info(
    *, redact_home: bool = False
) -> dict[str, str | bool | dict[str, Any]]:
    """
    Collect environment information for diagnostics.

    Args:
        redact_home (bool, optional): When True, abbreviate the marimo install
            location's home-directory prefix to `~`. Defaults to False.

    Returns:
        dict: Environment information keyed by field name.
    """
    os_version = platform.release()
    if platform.system() == "Windows" and is_win11():
        os_version = "11"

    location = Path(__file__).parent.parent.as_posix()
    if redact_home:
        location = abbreviate_home(location)

    info: dict[str, str | bool | dict[str, Any]] = {
        "marimo": __version__,
        "editable": is_editable("marimo"),
        "location": location,
        "OS": platform.system(),
        "OS Version": os_version,
        # e.g., x86 or arm
        "Processor": platform.processor(),
        "Python Version": platform.python_version(),
        "Locale": get_default_locale(),
    }

    binaries = {
        # Check chrome specifically if invoked from cli, this value could be
        # back-filled in frontend
        "Browser": get_chrome_version() or "--",
        "Node": get_node_version() or "--",
        "uv": get_uv_version() or "--",
    }

    requirements = get_required_modules_list()
    optional_deps = get_optional_modules_list()
    experimental = get_experimental_flags()
    return {
        **info,
        "Binaries": binaries,
        "Dependencies": requirements,
        "Optional Dependencies": optional_deps,
        "Experimental Flags": experimental,
    }
