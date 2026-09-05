# Copyright 2026 Marimo. All rights reserved.
"""What marimo layers into sandbox launches."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._utils.versions import is_editable
from marimo._version import __version__

if TYPE_CHECKING:
    from collections.abc import Sequence

LOGGER = _loggers.marimo_logger()


def marimo_dir() -> Path:
    """The repository root when marimo runs from a checkout."""
    return Path(__file__).parent.parent.parent


def runtime_overlay(
    features: Sequence[str] = (),
    additional_deps: Sequence[str] = (),
) -> list[str]:
    """The requirements marimo layers into a sandbox launch.

    marimo itself rides the overlay, pinned to the running version or as
    an editable install from a development checkout, so the launched
    process matches the CLI regardless of what a manifest's `marimo`
    resolves to. Overlay entries never enter the manifest.
    """
    if is_editable("marimo"):
        LOGGER.info("Using editable of marimo for sandbox")
        marimo_dep = f"-e {marimo_dir()}"
    elif features:
        marimo_dep = f"marimo[{','.join(features)}]=={__version__}"
    else:
        marimo_dep = f"marimo=={__version__}"
    return [marimo_dep, *additional_deps]
