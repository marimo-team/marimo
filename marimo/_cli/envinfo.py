# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import platform
import sys
from typing import Any, Union, cast

from marimo import __version__
from marimo._utils.health import (
    get_chrome_version,
    get_node_version,
    get_required_modules_list,
)


def is_win11() -> bool:
    """
    Check if the operating system is Windows 11.

    Returns:
        bool: True if the OS is Windows 11, False otherwise.
    """
    if hasattr(sys, "getwindowsversion"):
        return cast(Any, sys).getwindowsversion().build >= 22000  # type: ignore[no-any-return]
    return False


def get_system_info() -> dict[str, Union[str, dict[str, str]]]:
    os_version = platform.release()
    if platform.system() == "Windows" and is_win11():
        os_version = "11"

    info = {
        "marimo": __version__,
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

    return {**info, "Binaries": binaries, "Requirements": requirements}
