# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

__all__ = ["MissingModule", "ModuleStub"]


class MissingModule(ModuleType):
    """Placeholder for a cached module def that is unimportable here.

    Enables loading a cache lazily until a module is actually needed.
    """

    def __init__(self, name: str, version: str = "") -> None:
        super().__init__(name)
        self.__missing__ = True
        # Replay the pinned version captured at cache time so a version-pinned
        # content hash reproduces here even though the real module is absent.
        # Set as a concrete attribute so it resolves without hitting the
        # `__getattr__` fallback below (which rejects dunder probes).
        self.__version__ = version

    def __getattr__(self, attr: str) -> Any:
        if attr.startswith("__") and attr.endswith("__"):
            # Dunder probes — pickling machinery, repr, and
            # getattr-with-default version lookups — must fall back
            # rather than propagate an import error.
            raise AttributeError(attr)
        raise ModuleNotFoundError(
            f"No module named {self.__name__!r} in this environment "
            f"(cached def restored lazily; accessing "
            f"{self.__name__}.{attr} requires the real module)"
        )


class ModuleStub:
    """Stub for module objects, storing only the module name."""

    def __init__(
        self,
        module: Any,
        hash: str = "",  # noqa: A002
        version: str = "",
    ) -> None:
        self.name = module.__name__
        self.hash = hash
        # `str(...)`: some packages expose a non-str `__version__` (e.g.
        # torch's `TorchVersion`) that the manifest codec can't encode.
        self.version = str(version or getattr(module, "__version__", "") or "")

    def load(self) -> Any:
        """Reload the module by name.

        Falls back to a `MissingModule` placeholder when the module itself
        is absent, so restoration succeeds and the error surfaces only on
        actual use. A `ModuleNotFoundError` for a *different* module — i.e.
        a transitive import the module performs internally — is re-raised
        rather than masked as "this module is missing".
        """
        try:
            return importlib.import_module(self.name)
        except ModuleNotFoundError as e:
            missing = getattr(e, "name", None)
            if (
                missing is None
                or missing == self.name
                or self.name.startswith(f"{missing}.")
            ):
                return MissingModule(self.name, self.version)
            raise
