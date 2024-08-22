from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class GlobalSettings:
    DEVELOPMENT_MODE: bool = False
    QUIET: bool = False
    CHECK_STATUS_UPDATE: bool = False
    CAPTURE_TRACES: bool = (
        os.getenv("MARIMO_CAPTURE_TRACES", "false") == "true"
    )


GLOBAL_SETTINGS = GlobalSettings()
