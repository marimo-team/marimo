# Copyright 2026 Marimo. All rights reserved.
# NB. test_cli_errors.py because test_errors.py name causes pycache errors
# with pytest.
from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch

from marimo._cli.errors import MarimoCLIError, MarimoCLIMissingDependencyError


def test_missing_dependency_error_renders_followup_commands() -> None:
    with patch(
        "marimo._cli.errors.get_install_commands",
        return_value=[
            "poetry add nbconvert[webpdf]",
            "python -m pip install nbconvert[webpdf]",
        ],
    ):
        error = MarimoCLIMissingDependencyError(
            "Playwright is required for WebPDF export.",
            "nbconvert[webpdf]",
            followup_commands=[
                "poetry run playwright install chromium",
                "python -m playwright install chromium",
            ],
        )

    message = str(error)
    assert "Tip: Install with:" in message
    assert "poetry add nbconvert[webpdf]" in message
    assert "Or with pip:" in message
    assert "Then run:" in message
    assert "poetry run playwright install chromium" in message
    assert "Or with fallback:" in message
    assert "python -m playwright install chromium" in message


def test_missing_dependency_error_preserves_additional_tip() -> None:
    with patch(
        "marimo._cli.errors.get_install_commands",
        return_value=["python -m pip install uv"],
    ):
        error = MarimoCLIMissingDependencyError(
            "uv must be installed to use --sandbox.",
            "uv",
            additional_tip="Install uv from https://github.com/astral-sh/uv",
        )

    message = str(error)
    assert "python -m pip install uv" in message
    assert "Install uv from https://github.com/astral-sh/uv" in message


def test_chromium_setup_command_not_hardcoded_in_export_callsites() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    export_commands = (
        repo_root / "marimo" / "_cli" / "export" / "commands.py"
    ).read_text(encoding="utf-8")
    export_thumbnail = (
        repo_root / "marimo" / "_cli" / "export" / "thumbnail.py"
    ).read_text(encoding="utf-8")
    assert "python -m playwright install chromium" not in export_commands
    assert "python -m playwright install chromium" not in export_thumbnail


def test_marimo_cli_error_show_formats_error_prefix() -> None:
    error = MarimoCLIError("boom")
    output = StringIO()

    with patch("marimo._cli.errors.red", return_value="<error>") as mock_red:
        error.show(file=output)

    mock_red.assert_called_once_with("Error", bold=True)
    assert output.getvalue() == "<error>: boom\n"
