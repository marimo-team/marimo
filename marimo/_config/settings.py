# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import logging
import os
from dataclasses import dataclass


@dataclass
class GlobalSettings:
    DEVELOPMENT_MODE: bool = False
    QUIET: bool = False
    CHECK_STATUS_UPDATE: bool = False
    TRACING: bool = os.getenv("MARIMO_TRACING", "false") in ("true", "1")
    PROFILE_DIR: str | None = None
    LOG_LEVEL: int = logging.WARNING


GLOBAL_SETTINGS = GlobalSettings()
