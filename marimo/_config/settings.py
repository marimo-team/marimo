# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GlobalSettings:
    DEVELOPMENT_MODE: bool = False
    QUIET: bool = False
    CHECK_STATUS_UPDATE: bool = False


GLOBAL_SETTINGS = GlobalSettings()
