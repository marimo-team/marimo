# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import importlib
from typing import Any

__all__ = ["ModuleStub"]


class ModuleStub:
    """Stub for module objects, storing only the module name."""

    def __init__(self, module: Any) -> None:
        self.name = module.__name__

    def load(self) -> Any:
        """Reload the module by name."""
        return importlib.import_module(self.name)
