# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import platform
import sys
from typing import Any, Union, cast

from marimo import _loggers
from marimo._config.manager import get_default_config_manager
from marimo._utils.health import (
    get_chrome_version,
    get_node_version,
    get_optional_modules_list,
    get_required_modules_list,
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


def get_experimental_flags() -> dict[str, bool]:
    try:
        config = get_default_config_manager(current_path=None).get_config()
        if "experimental" in config:
            return config["experimental"]
        else:
            return {}
    except Exception:
        LOGGER.error("Failed to get experimental flags")
        return {}


def get_system_info() -> dict[str, Union[str, bool, dict[str, Any]]]:
    os_version = platform.release()
    if platform.system() == "Windows" and is_win11():
        os_version = "11"

    info: dict[str, Union[str, bool, dict[str, Any]]] = {
        "marimo": __version__,
        "editable": is_editable("marimo"),
        "OS": platform.system(),
        "OS Version": os_version,
        # e.g., x86 or arm
        "Processor": platform.processor(),
        "Python Version": platform.python_version(),
    }

    binaries = {
        # Check chrome specifically if invoked from cli, this value could be
        # back-filled in frontend
        "Browser": get_chrome_version() or "--",
        "Node": get_node_version() or "--",
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
