# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from typing import cast

from marimo import _loggers
from marimo._cli.install_hints import (
    get_playwright_chromium_setup_commands,
)
from marimo._dependencies.dependencies import (
    DependencyLike,
    DependencyManager,
    DependencyRequirement,
)
from marimo._schemas.export import ExportSetupRequirement
from marimo._schemas.export_options import ServerExportFormat
from marimo._utils.assert_never import assert_never
from marimo._utils.async_path import isfile

LOGGER = _loggers.marimo_logger()

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


async def get_missing_export_setup(
    export_format: ServerExportFormat,
) -> list[ExportSetupRequirement]:
    """Return missing runtime setup for an export format."""
    if export_format != "pdf" or not DependencyManager.playwright.has():
        return []

    try:
        chromium_installed = await _is_playwright_chromium_installed()
    except Exception as e:
        LOGGER.warning(
            "Failed to check whether Playwright Chromium is installed",
            exc_info=e,
        )
        chromium_installed = False

    if chromium_installed:
        return []

    return [
        ExportSetupRequirement(
            name="playwright-chromium",
            command=get_playwright_chromium_setup_commands()[0],
        )
    ]


async def _is_playwright_chromium_installed() -> bool:
    """Return whether Playwright's matching Chromium executable exists."""
    executable = (
        await asyncio.to_thread(_get_playwright_chromium_executable_on_windows)
        if sys.platform == "win32"
        else await _get_playwright_chromium_executable()
    )
    return await isfile(executable)


async def _get_playwright_chromium_executable() -> str:
    """Return the executable expected by the installed Playwright version."""

    from playwright.async_api import (  # type: ignore[import-not-found]
        async_playwright,
    )

    async with async_playwright() as playwright:
        return cast(str, playwright.chromium.executable_path)


def _get_playwright_chromium_executable_on_windows() -> str:
    # The server uses a Windows SelectorEventLoop, which cannot start the
    # Playwright driver subprocess. This worker thread owns a Proactor loop.
    assert sys.platform == "win32"
    loop = asyncio.ProactorEventLoop()  # type: ignore[attr-defined]
    try:
        return cast(
            str,
            loop.run_until_complete(_get_playwright_chromium_executable()),
        )
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


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
