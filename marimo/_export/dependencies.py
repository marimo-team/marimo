# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import get_args

from marimo._dependencies.dependencies import (
    DependencyLike,
    DependencyManager,
    DependencyRequirement,
)
from marimo._schemas.export_options import ServerExportFormat

_IPYNB_DEPENDENCIES = (DependencyManager.nbformat,)

EXPORT_DEPENDENCY_REQUIREMENTS: dict[
    ServerExportFormat, tuple[DependencyLike, ...]
] = {
    "html": (),
    "markdown": (),
    "ipynb": _IPYNB_DEPENDENCIES,
    "pdf": (
        DependencyRequirement(
            package="nbconvert[webpdf]",
            dependencies=(
                *_IPYNB_DEPENDENCIES,
                DependencyManager.nbconvert,
                DependencyManager.playwright,
            ),
        ),
    ),
}

SERVER_EXPORT_FORMATS: tuple[ServerExportFormat, ...] = get_args(
    ServerExportFormat
)


def missing_export_packages(export_format: ServerExportFormat) -> list[str]:
    """Return missing package specifications for an export format."""
    return DependencyManager.missing_packages(
        *EXPORT_DEPENDENCY_REQUIREMENTS[export_format]
    )


def require_export_dependencies(
    export_format: ServerExportFormat,
    why: str,
) -> None:
    """Require the server dependencies for an export format."""
    DependencyManager.require_many(
        why,
        *EXPORT_DEPENDENCY_REQUIREMENTS[export_format],
        source="server",
    )
