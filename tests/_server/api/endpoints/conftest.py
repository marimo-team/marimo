# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._dependencies.dependencies import DependencyManager

# These modules import pydantic at import time, so they cannot be collected
# where it is not installed (no cp315 wheels yet).
collect_ignore = [] if DependencyManager.pydantic.has() else ["test_ai.py"]
