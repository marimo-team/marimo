# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._dependencies.dependencies import (
    DependencyLike,
    DependencyManager,
    DependencyRequirement,
)
from marimo._schemas.export_options import ServerExportFormat
from marimo._utils.assert_never import assert_never

_IPYNB_DEPENDENCIES = (DependencyManager.nbformat,)
_PDF_DEPENDENCIES = (
    DependencyRequirement(
        package="nbconvert[webpdf]",
        dependencies=(
            *_IPYNB_DEPENDENCIES,
            DependencyManager.nbconvert,
            DependencyManager.playwright,
        ),
    ),
)


def _dependencies_for_format(
    export_format: ServerExportFormat,
) -> tuple[DependencyLike, ...]:
    match export_format:
        case "html":
            return ()
        case "markdown":
            return ()
        case "script":
            return ()
        case "ipynb":
            return _IPYNB_DEPENDENCIES
        case "pdf":
            return _PDF_DEPENDENCIES
        case _:
            assert_never(export_format)


def get_missing_export_packages(
    export_format: ServerExportFormat,
) -> list[str]:
    """Return missing package specifications for an export format."""
    return DependencyManager.missing_packages(
        *_dependencies_for_format(export_format)
    )


def require_export_dependencies(
    export_format: ServerExportFormat,
    why: str,
) -> None:
    """Require the server dependencies for an export format."""
    DependencyManager.require_many(
        why,
        *_dependencies_for_format(export_format),
        source="server",
    )
