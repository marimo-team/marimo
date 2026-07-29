# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import get_args
from unittest.mock import patch

import pytest

from marimo._ast.app import App, InternalApp
from marimo._dependencies.dependencies import DependencyManager
from marimo._dependencies.errors import ManyModulesNotFoundError
from marimo._export.dependencies import (
    EXPORT_DEPENDENCY_REQUIREMENTS,
    SERVER_EXPORT_FORMATS,
    missing_export_packages,
    require_export_dependencies,
)
from marimo._export.exporter import Exporter
from marimo._export.requests import IPYNBExportRequest
from marimo._schemas.export_options import (
    IPYNBExportOptions,
    ServerExportFormat,
)


def test_export_requirement_registry_covers_server_formats() -> None:
    assert (
        tuple(EXPORT_DEPENDENCY_REQUIREMENTS)
        == get_args(ServerExportFormat)
        == SERVER_EXPORT_FORMATS
    )


def test_export_requirements_when_dependencies_are_installed() -> None:
    with (
        patch.object(DependencyManager.nbformat, "has", return_value=True),
        patch.object(DependencyManager.nbconvert, "has", return_value=True),
        patch.object(DependencyManager.playwright, "has", return_value=True),
    ):
        assert {
            export_format: missing_export_packages(export_format)
            for export_format in SERVER_EXPORT_FORMATS
        } == {
            "html": [],
            "markdown": [],
            "ipynb": [],
            "pdf": [],
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
        assert missing_export_packages("pdf") == ["nbconvert[webpdf]"]


def test_ipynb_requirement_uses_nbformat() -> None:
    with patch.object(DependencyManager.nbformat, "has", return_value=False):
        assert missing_export_packages("ipynb") == ["nbformat"]


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
