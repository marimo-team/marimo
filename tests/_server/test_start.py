# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._environments.sandbox import Backend
from marimo._server.start import start
from marimo._server.tokens import AuthToken
from marimo._server.workspace import DirectoryWorkspace
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("sandbox", "inherited_backend", "expected_manager"),
    [
        ("uv", None, "uv"),
        ("pixi", None, "pixi"),
        (None, "uv", "uv"),
        (None, "pixi", "pixi"),
        (None, None, "pip"),
    ],
)
def test_package_manager_follows_sandbox_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sandbox: Backend | None,
    inherited_backend: Backend | None,
    expected_manager: str,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.marimo.package_management]\nmanager = "pip"\n'
    )
    monkeypatch.delenv("MARIMO_ANCESTOR_PID", raising=False)
    for setting, value in {
        "SANDBOX_BACKEND": inherited_backend,
        "SANDBOX_MODE": "single" if inherited_backend else None,
        "MANAGE_SCRIPT_METADATA": inherited_backend is not None,
    }.items():
        monkeypatch.setattr(GLOBAL_SETTINGS, setting, value)
        monkeypatch.delenv(f"MARIMO_{setting}", raising=False)

    with (
        patch("marimo._server.start.CompositeLspServer"),
        patch("marimo._server.start.initialize_fd_limit"),
        patch("marimo._server.start.initialize_signals"),
        patch("marimo._server.start.uvicorn.Server", autospec=True) as server,
    ):
        start(
            workspace=DirectoryWorkspace(
                str(tmp_path), include_markdown=False
            ),
            mode=SessionMode.EDIT,
            development_mode=False,
            quiet=True,
            include_code=True,
            ttl_seconds=None,
            headless=True,
            port=2718,
            host="127.0.0.1",
            proxy=None,
            watch=False,
            cli_args={},
            argv=[],
            auth_token=AuthToken(""),
            redirect_console_to_browser=False,
            skew_protection=False,
            sandbox=sandbox,
        )

    app = server.call_args.args[0].app
    assert app.state.config_manager.get_config()["package_management"] == {
        "manager": expected_manager
    }
