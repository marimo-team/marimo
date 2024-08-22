# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class GlobalSettings:
    DEVELOPMENT_MODE: bool = False
    QUIET: bool = False
    CHECK_STATUS_UPDATE: bool = False
    TRACING: bool = os.getenv("MARIMO_TRACING", "false") in ("true", "1")


GLOBAL_SETTINGS = GlobalSettings()
