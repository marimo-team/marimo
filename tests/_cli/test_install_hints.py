# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import patch

from marimo._cli.install_hints import (
    get_install_commands,
    get_playwright_chromium_setup_commands,
    get_post_install_commands,
    get_upgrade_commands,
)


def test_install_commands_uv_project() -> None:
    with (
        patch(
            "marimo._cli.install_hints.infer_package_manager",
            return_value="uv",
        ),
        patch(
            "marimo._cli.install_hints._is_uv_project_context",
            return_value=True,
        ),
    ):
        assert get_install_commands("rich") == [
            "uv add rich",
            "python -m pip install rich",
        ]


def test_install_commands_uv_non_project() -> None:
    with (
        patch(
            "marimo._cli.install_hints.infer_package_manager",
            return_value="uv",
        ),
        patch(
            "marimo._cli.install_hints._is_uv_project_context",
            return_value=False,
        ),
    ):
        assert get_install_commands("rich") == [
            "uv pip install rich",
            "python -m pip install rich",
        ]


def test_install_commands_for_pixi() -> None:
    with patch(
        "marimo._cli.install_hints.infer_package_manager",
        return_value="pixi",
    ):
        assert get_install_commands("nbconvert playwright") == [
            "pixi add nbconvert playwright",
            "python -m pip install nbconvert playwright",
        ]


def test_install_commands_for_pip_only() -> None:
    with patch(
        "marimo._cli.install_hints.infer_package_manager",
        return_value="pip",
    ):
        assert get_install_commands(["nbformat"]) == [
            "python -m pip install nbformat"
        ]


def test_post_install_commands_uv_project() -> None:
    with (
        patch(
            "marimo._cli.install_hints.infer_package_manager",
            return_value="uv",
        ),
        patch(
            "marimo._cli.install_hints._is_uv_project_context",
            return_value=True,
        ),
    ):
        assert get_post_install_commands(
            "playwright install chromium",
            module_fallback="python -m playwright install chromium",
        ) == [
            "uv run playwright install chromium",
            "python -m playwright install chromium",
        ]


def test_post_install_commands_uv_non_project() -> None:
    with (
        patch(
            "marimo._cli.install_hints.infer_package_manager",
            return_value="uv",
        ),
        patch(
            "marimo._cli.install_hints._is_uv_project_context",
            return_value=False,
        ),
    ):
        assert get_post_install_commands(
            "playwright install chromium",
            module_fallback="python -m playwright install chromium",
        ) == ["python -m playwright install chromium"]


def test_post_install_commands_poetry() -> None:
    with patch(
        "marimo._cli.install_hints.infer_package_manager",
        return_value="poetry",
    ):
        assert get_post_install_commands(
            "playwright install chromium",
            module_fallback="python -m playwright install chromium",
        ) == [
            "poetry run playwright install chromium",
            "python -m playwright install chromium",
        ]


def test_upgrade_commands_uv_project() -> None:
    with (
        patch(
            "marimo._cli.install_hints.infer_package_manager",
            return_value="uv",
        ),
        patch(
            "marimo._cli.install_hints._is_uv_project_context",
            return_value=True,
        ),
    ):
        assert get_upgrade_commands("marimo") == [
            "uv add --upgrade marimo",
            "python -m pip install --upgrade marimo",
        ]


def test_upgrade_commands_uv_non_project() -> None:
    with (
        patch(
            "marimo._cli.install_hints.infer_package_manager",
            return_value="uv",
        ),
        patch(
            "marimo._cli.install_hints._is_uv_project_context",
            return_value=False,
        ),
    ):
        assert get_upgrade_commands("marimo") == [
            "uv pip install --upgrade marimo",
            "python -m pip install --upgrade marimo",
        ]


def test_upgrade_commands_for_pixi() -> None:
    with patch(
        "marimo._cli.install_hints.infer_package_manager",
        return_value="pixi",
    ):
        assert get_upgrade_commands("marimo") == [
            "pixi upgrade marimo",
            "python -m pip install --upgrade marimo",
        ]


def test_upgrade_commands_for_pip_only() -> None:
    with patch(
        "marimo._cli.install_hints.infer_package_manager",
        return_value="pip",
    ):
        assert get_upgrade_commands(["marimo"]) == [
            "python -m pip install --upgrade marimo"
        ]


def test_playwright_chromium_setup_commands() -> None:
    with patch(
        "marimo._cli.install_hints.infer_package_manager",
        return_value="pip",
    ):
        assert get_playwright_chromium_setup_commands() == [
            "python -m playwright install chromium"
        ]


def test_install_commands_quotes_extras_on_posix() -> None:
    with (
        patch(
            "marimo._cli.install_hints.infer_package_manager",
            return_value="uv",
        ),
        patch(
            "marimo._cli.install_hints._is_uv_project_context",
            return_value=True,
        ),
        patch("marimo._cli.install_hints.is_windows", return_value=False),
    ):
        assert get_install_commands(["marimo[sandbox]", "pyzmq"]) == [
            "uv add 'marimo[sandbox]' pyzmq",
            "python -m pip install 'marimo[sandbox]' pyzmq",
        ]


def test_install_commands_does_not_quote_extras_on_windows() -> None:
    with (
        patch(
            "marimo._cli.install_hints.infer_package_manager",
            return_value="uv",
        ),
        patch(
            "marimo._cli.install_hints._is_uv_project_context",
            return_value=True,
        ),
        patch("marimo._cli.install_hints.is_windows", return_value=True),
    ):
        assert get_install_commands(["marimo[sandbox]", "pyzmq"]) == [
            "uv add marimo[sandbox] pyzmq",
            "python -m pip install marimo[sandbox] pyzmq",
        ]
