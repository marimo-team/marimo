# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.packages.module_name_to_pypi_name import (
    module_name_to_pypi_name,
)


def module_name_to_conda_name() -> dict[str, str]:
    # as a heuristic, start with pypi mapping and sub out things
    # that known to be incorrect; this doesn't handle channels ...
    mapping = module_name_to_pypi_name()
    mapping["cv2"] = "opencv"
    return mapping
