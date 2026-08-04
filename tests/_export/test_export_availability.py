# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._ast.app import App, InternalApp
from marimo._dependencies.dependencies import DependencyManager
from marimo._dependencies.errors import ManyModulesNotFoundError
from marimo._export.dependencies import (
    _get_playwright_chromium_executable_on_windows,
    _is_playwright_chromium_installed,
    get_missing_export_packages,
    get_missing_export_setup,
    require_export_dependencies,
)
from marimo._export.exporter import Exporter
from marimo._export.requests import IPYNBExportRequest
from marimo._schemas.export import ExportSetupRequirement
from marimo._schemas.export_options import (
    SERVER_EXPORT_FORMATS,
    IPYNBExportOptions,
)


def test_export_requirements_when_dependencies_are_installed() -> None:
    with (
        patch.object(DependencyManager.nbformat, "has", return_value=True),
        patch.object(DependencyManager.nbconvert, "has", return_value=True),
        patch.object(DependencyManager.playwright, "has", return_value=True),
    ):
        assert {
            export_format: get_missing_export_packages(export_format)
            for export_format in SERVER_EXPORT_FORMATS
        } == {
            "html": [],
            "markdown": [],
            "ipynb": [],
            "pdf": [],
            "script": [],
        }


@pytest.mark.parametrize(
    ("nbformat", "nbconvert", "playwright"),
    [
        (False, True, True),
        (True, False, True),
        (True, True, False),
        (False, False, False),
    ],
)
def test_pdf_requirement_is_an_actionable_package_spec(
    *,
    nbformat: bool,
    nbconvert: bool,
    playwright: bool,
) -> None:
    with (
        patch.object(DependencyManager.nbformat, "has", return_value=nbformat),
        patch.object(
            DependencyManager.nbconvert, "has", return_value=nbconvert
        ),
        patch.object(
            DependencyManager.playwright, "has", return_value=playwright
        ),
    ):
        assert get_missing_export_packages("pdf") == ["nbconvert[webpdf]"]


def test_ipynb_requirement_uses_nbformat() -> None:
    with patch.object(DependencyManager.nbformat, "has", return_value=False):
        assert get_missing_export_packages("ipynb") == ["nbformat"]


@pytest.mark.parametrize(
    ("chromium_installed", "missing_setup"),
    [
        (True, []),
        (
            False,
            [
                ExportSetupRequirement(
                    name="playwright-chromium",
                    command="uv run playwright install chromium",
                )
            ],
        ),
    ],
)
async def test_pdf_setup_requires_playwright_chromium(
    *,
    chromium_installed: bool,
    missing_setup: list[ExportSetupRequirement],
) -> None:
    with (
        patch.object(DependencyManager.playwright, "has", return_value=True),
        patch(
            "marimo._export.dependencies._is_playwright_chromium_installed",
            new=AsyncMock(return_value=chromium_installed),
        ),
        patch(
            "marimo._export.dependencies.get_playwright_chromium_setup_commands",
            return_value=["uv run playwright install chromium"],
        ),
    ):
        assert await get_missing_export_setup("pdf") == missing_setup


async def test_pdf_setup_is_deferred_until_playwright_is_installed() -> None:
    probe = AsyncMock()
    with (
        patch.object(DependencyManager.playwright, "has", return_value=False),
        patch(
            "marimo._export.dependencies._is_playwright_chromium_installed",
            new=probe,
        ),
    ):
        assert await get_missing_export_setup("pdf") == []
    probe.assert_not_awaited()


async def test_chromium_probe_checks_playwright_executable() -> None:
    context = MagicMock()
    context.__aenter__.return_value = SimpleNamespace(
        chromium=SimpleNamespace(executable_path="/playwright/chromium")
    )
    async_api = MagicMock()
    async_api.async_playwright.return_value = context
    is_file = AsyncMock(return_value=True)

    with (
        patch.dict(
            sys.modules,
            {
                "playwright": MagicMock(),
                "playwright.async_api": async_api,
            },
        ),
        patch("marimo._export.dependencies.sys.platform", "linux"),
        patch("marimo._export.dependencies.isfile", new=is_file),
    ):
        assert await _is_playwright_chromium_installed() is True

    async_api.async_playwright.assert_called_once_with()
    context.__aexit__.assert_awaited_once()
    is_file.assert_awaited_once_with("/playwright/chromium")


async def test_chromium_probe_uses_proactor_worker_on_windows() -> None:
    to_thread = AsyncMock(return_value="C:/playwright/chromium.exe")
    is_file = AsyncMock(return_value=True)
    with (
        patch("marimo._export.dependencies.sys.platform", "win32"),
        patch("marimo._export.dependencies.asyncio.to_thread", new=to_thread),
        patch("marimo._export.dependencies.isfile", new=is_file),
    ):
        assert await _is_playwright_chromium_installed() is True

    to_thread.assert_awaited_once_with(
        _get_playwright_chromium_executable_on_windows
    )
    is_file.assert_awaited_once_with("C:/playwright/chromium.exe")


def test_windows_chromium_probe_owns_proactor_loop() -> None:
    loop = MagicMock()
    loop.run_until_complete.side_effect = [
        "C:/playwright/chromium.exe",
        None,
    ]
    loop.shutdown_asyncgens = AsyncMock()

    with (
        patch("marimo._export.dependencies.sys.platform", "win32"),
        patch.object(
            asyncio,
            "ProactorEventLoop",
            create=True,
            return_value=loop,
        ),
    ):
        assert (
            _get_playwright_chromium_executable_on_windows()
            == "C:/playwright/chromium.exe"
        )

    for call in loop.run_until_complete.call_args_list:
        call.args[0].close()
    loop.close.assert_called_once_with()


def test_ipynb_export_requires_server_dependency() -> None:
    with (
        patch.object(DependencyManager.nbformat, "has", return_value=False),
        pytest.raises(ManyModulesNotFoundError) as exc_info,
    ):
        Exporter().export_as_ipynb(
            IPYNBExportRequest(
                app=InternalApp(App()),
                options=IPYNBExportOptions(sort_mode="top-down"),
            )
        )

    assert exc_info.value.package_names == ["nbformat"]
    assert exc_info.value.source == "server"


def test_require_export_dependencies_reports_server_source() -> None:
    with (
        patch.object(DependencyManager.nbformat, "has", return_value=True),
        patch.object(DependencyManager.nbconvert, "has", return_value=True),
        patch.object(DependencyManager.playwright, "has", return_value=False),
        pytest.raises(ManyModulesNotFoundError) as exc_info,
    ):
        require_export_dependencies("pdf", "for PDF export")

    assert exc_info.value.package_names == ["nbconvert[webpdf]"]
    assert exc_info.value.source == "server"
    assert (
        str(exc_info.value)
        == "The following packages are required for PDF export: "
        "nbconvert[webpdf]"
    )
