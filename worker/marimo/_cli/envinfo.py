# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import platform
from typing import Union

from marimo import __version__
from marimo._utils.health import (
    get_chrome_version,
    get_node_version,
    get_required_modules_list,
)


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
        # Check chrome specifically if invoked from cli, this value could be
        # back-filled in frontend
        "Browser": get_chrome_version() or "--",
        "Node": get_node_version() or "--",
    }

    requirements = get_required_modules_list()

    return {**info, "Binaries": binaries, "Requirements": requirements}
