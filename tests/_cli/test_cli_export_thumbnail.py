# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

import marimo._cli.export.thumbnail as thumbnail_module
from marimo._cli.sandbox import SandboxMode

if TYPE_CHECKING:
    from pathlib import Path


def _write_notebook(path: Path) -> None:
    path.write_text(
        """
import marimo

app = marimo.App()

@app.cell
def _():
    return

if __name__ == "__main__":
    app.run()
""",
        encoding="utf-8",
    )


def test_thumbnail_sandbox_single_bootstrap_adds_playwright(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "notebook.py"
    _write_notebook(notebook)
    runner = CliRunner()

    captured: dict[str, str | list[str] | None] = {}

    def _fake_run_in_sandbox(
        args: list[str],
        *,
        name: str | None = None,
        additional_features: list[str] | None = None,
        additional_deps: list[str] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> int:
        del args
        del additional_features
        captured["name"] = name
        captured["deps"] = additional_deps
        captured["mode"] = (extra_env or {}).get(
            thumbnail_module._sandbox_mode_env
        )
        captured["bootstrapped"] = (extra_env or {}).get(
            thumbnail_module._sandbox_bootstrapped_env
        )
        return 0

    with (
        patch(
            "marimo._cli.sandbox.run_in_sandbox",
            side_effect=_fake_run_in_sandbox,
        ) as run_in_sandbox,
        patch(
            "marimo._cli.sandbox.resolve_sandbox_mode",
            return_value=SandboxMode.SINGLE,
        ),
        patch.object(
            thumbnail_module.DependencyManager.playwright, "require"
        ) as playwright_require,
    ):
        result = runner.invoke(
            thumbnail_module.thumbnail,
            [str(notebook), "--execute", "--sandbox"],
        )

    assert result.exit_code == 0, result.output
    run_in_sandbox.assert_called_once()
    playwright_require.assert_not_called()
    assert captured["name"] == str(notebook)
    assert captured["deps"] == ["playwright"]
    assert captured["mode"] == SandboxMode.SINGLE.value
    assert captured["bootstrapped"] == "1"
    assert thumbnail_module._sandbox_bootstrapped_env not in os.environ
    assert thumbnail_module._sandbox_mode_env not in os.environ


def test_thumbnail_sandbox_multi_bootstrap_sets_multi_mode(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    _write_notebook(first)
    _write_notebook(second)
    runner = CliRunner()

    captured: dict[str, str | list[str] | None] = {}

    def _fake_run_in_sandbox(
        args: list[str],
        *,
        name: str | None = None,
        additional_features: list[str] | None = None,
        additional_deps: list[str] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> int:
        del args
        del additional_features
        captured["name"] = name
        captured["deps"] = additional_deps
        captured["mode"] = (extra_env or {}).get(
            thumbnail_module._sandbox_mode_env
        )
        return 0

    with (
        patch(
            "marimo._cli.sandbox.run_in_sandbox",
            side_effect=_fake_run_in_sandbox,
        ) as run_in_sandbox,
        patch("marimo._cli.sandbox.resolve_sandbox_mode") as resolve_mode,
        patch.object(
            thumbnail_module.DependencyManager.playwright, "require"
        ) as playwright_require,
    ):
        result = runner.invoke(
            thumbnail_module.thumbnail,
            [str(first), str(second), "--execute", "--sandbox"],
        )

    assert result.exit_code == 0, result.output
    run_in_sandbox.assert_called_once()
    resolve_mode.assert_not_called()
    playwright_require.assert_not_called()
    assert captured["name"] == str(first)
    assert captured["deps"] == ["playwright"]
    assert captured["mode"] == SandboxMode.MULTI.value


def test_thumbnail_sandbox_requires_execute(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.py"
    _write_notebook(notebook)
    runner = CliRunner()

    result = runner.invoke(
        thumbnail_module.thumbnail,
        [str(notebook), "--sandbox"],
    )

    assert result.exit_code != 0
    assert "--sandbox requires --execute" in result.output


def test_thumbnail_reentry_single_skips_bootstrap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    notebook = tmp_path / "notebook.py"
    _write_notebook(notebook)
    runner = CliRunner()
    generate = AsyncMock()

    monkeypatch.setenv(thumbnail_module._sandbox_bootstrapped_env, "1")
    monkeypatch.setenv(
        thumbnail_module._sandbox_mode_env,
        SandboxMode.SINGLE.value,
    )

    with (
        patch("marimo._cli.sandbox.run_in_sandbox") as run_in_sandbox,
        patch("marimo._cli.sandbox.resolve_sandbox_mode") as resolve_mode,
        patch.object(
            thumbnail_module.DependencyManager.playwright, "require"
        ) as playwright_require,
        patch.object(thumbnail_module, "_generate_thumbnails", new=generate),
    ):
        result = runner.invoke(
            thumbnail_module.thumbnail,
            [str(notebook), "--execute"],
        )

    assert result.exit_code == 0, result.output
    run_in_sandbox.assert_not_called()
    resolve_mode.assert_not_called()
    playwright_require.assert_called_once_with("for thumbnail generation")
    generate.assert_called_once()
    assert generate.call_args.kwargs["sandbox_mode"] is SandboxMode.SINGLE


def test_thumbnail_reentry_multi_skips_bootstrap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    _write_notebook(first)
    _write_notebook(second)
    runner = CliRunner()
    generate = AsyncMock()

    monkeypatch.setenv(thumbnail_module._sandbox_bootstrapped_env, "1")
    monkeypatch.setenv(
        thumbnail_module._sandbox_mode_env,
        SandboxMode.MULTI.value,
    )

    with (
        patch("marimo._cli.sandbox.run_in_sandbox") as run_in_sandbox,
        patch("marimo._cli.sandbox.resolve_sandbox_mode") as resolve_mode,
        patch.object(
            thumbnail_module.DependencyManager.playwright, "require"
        ) as playwright_require,
        patch.object(thumbnail_module, "_generate_thumbnails", new=generate),
    ):
        result = runner.invoke(
            thumbnail_module.thumbnail,
            [str(first), str(second), "--execute"],
        )

    assert result.exit_code == 0, result.output
    run_in_sandbox.assert_not_called()
    resolve_mode.assert_not_called()
    playwright_require.assert_called_once_with("for thumbnail generation")
    generate.assert_called_once()
    assert generate.call_args.kwargs["sandbox_mode"] is SandboxMode.MULTI
