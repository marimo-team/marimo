from __future__ import annotations

import contextlib
import io
from unittest.mock import MagicMock, patch

import pytest

import marimo._code_mode as cm


@patch("marimo._code_mode._capabilities.get_entry_points")
def test_capabilities_lists_modules_without_loading(
    get_entry_points: MagicMock,
) -> None:
    first = MagicMock(name="first")
    first.name = "zeta"
    first.module = "zeta.agent"
    second = MagicMock(name="second")
    second.name = "alpha"
    second.module = "alpha.agent"
    duplicate = MagicMock(name="duplicate")
    duplicate.name = "alpha"
    duplicate.module = "alpha.agent"
    get_entry_points.return_value = [first, second, duplicate]

    assert cm.capabilities() == {
        "alpha": "alpha.agent",
        "zeta": "zeta.agent",
    }
    get_entry_points.assert_called_once_with("marimo.agent.capability")
    first.load.assert_not_called()
    second.load.assert_not_called()
    duplicate.load.assert_not_called()


@patch("marimo._code_mode._capabilities.get_entry_points")
def test_help_lists_installed_capability_modules_without_loading(
    get_entry_points: MagicMock,
) -> None:
    entry_point = MagicMock()
    entry_point.name = "lens"
    entry_point.module = "marimo_lens.agent"
    get_entry_points.return_value = [entry_point]

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        help(cm)

    assert "Installed capabilities:" in output.getvalue()
    assert "lens    import marimo_lens.agent" in output.getvalue()
    assert "help(module)" in output.getvalue()
    entry_point.load.assert_not_called()


@patch("marimo._code_mode._capabilities.get_entry_points")
def test_capabilities_rejects_conflicting_modules(
    get_entry_points: MagicMock,
) -> None:
    first = MagicMock()
    first.name = "lens"
    first.module = "first.agent"
    second = MagicMock()
    second.name = "lens"
    second.module = "second.agent"
    get_entry_points.return_value = [first, second]

    with pytest.raises(RuntimeError, match="Multiple capability modules"):
        cm.capabilities()
