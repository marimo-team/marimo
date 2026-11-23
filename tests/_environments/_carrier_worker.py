# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING

from marimo._environments import script_metadata

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event as ProcessEvent
    from threading import Event


def enter_carrier(
    notebook: str,
    attempting: Event | ProcessEvent,
    entered: Event | ProcessEvent,
    temporary_directory: str | None,
) -> None:
    # Keep the spawn target separate so children do not import pytest.
    if temporary_directory is not None:
        tempfile.tempdir = temporary_directory
    attempting.set()
    with script_metadata.materialized_for_environment(notebook):
        entered.set()
