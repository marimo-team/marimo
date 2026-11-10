# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._config.config_schema import PackageManagementConfig
from marimo._config.manager import get_default_config_manager
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._environments.sandbox import Backend
from marimo._server.start import start
from marimo._server.workspace import DirectoryWorkspace
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("mode", "sandbox", "inherited_backend", "expected_manager"),
    [
        (SessionMode.EDIT, "uv", None, "uv"),
        (SessionMode.EDIT, "pixi", None, "pixi"),
        (SessionMode.EDIT, None, "uv", "uv"),
        (SessionMode.EDIT, None, "pixi", "pixi"),
        (SessionMode.EDIT, None, None, "pip"),
        (SessionMode.RUN, "uv", None, "pip"),
        (SessionMode.RUN, "pixi", None, "pip"),
        (SessionMode.RUN, None, "uv", "uv"),
        (SessionMode.RUN, None, "pixi", "pixi"),
        (SessionMode.RUN, None, None, "pip"),
    ],
)
def test_package_manager_follows_sandbox_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sandbox: Backend | None,
    inherited_backend: Backend | None,
    expected_manager: str,
    mode: SessionMode,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".marimo.toml").write_text("")
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
            config_manager=get_default_config_manager(
                current_path=str(tmp_path)
            ).with_overrides({"server": {"headless": True, "port": 2718}}),
            mode=mode,
            development_mode=False,
            quiet=True,
            cli_args={},
            argv=[],
            sandbox=sandbox,
        )

    app = server.call_args.args[0].app
    assert (
        app.state.config_manager.get_config().package_management
        == PackageManagementConfig(manager=expected_manager)
    )

    session_manager = app.state.session_manager
    assert {
        "include_code": session_manager.include_code,
        "ttl_seconds": session_manager.ttl_seconds,
        "redirect_console_to_browser": session_manager.redirect_console_to_browser,
        "token_enabled": bool(session_manager.auth_token),
    } == {
        "include_code": mode == SessionMode.EDIT,
        "ttl_seconds": None if mode == SessionMode.EDIT else 120,
        "redirect_console_to_browser": mode == SessionMode.EDIT,
        "token_enabled": mode == SessionMode.EDIT,
    }


@pytest.mark.usefixtures("clean_config_environment")
@pytest.mark.parametrize("mode", [SessionMode.EDIT, SessionMode.RUN])
def test_start_uses_resolved_server_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: SessionMode
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".marimo.toml").write_text("")
    config_manager = get_default_config_manager(
        current_path=str(tmp_path)
    ).with_overrides(
        {
            "server": {
                "port": 3210,
                "headless": True,
                "proxy": "https://marimo.example/prefix",
                "token": False,
                "session_ttl": None,
                "include_code": False,
                "redirect_console_to_browser": False,
                "skew_protection": False,
            }
        }
    )
    with (
        patch("marimo._server.start.CompositeLspServer"),
        patch("marimo._server.start.initialize_fd_limit"),
        patch("marimo._server.start.initialize_signals"),
        patch("marimo._server.start.uvicorn.Server", autospec=True) as server,
    ):
        start(
            config_manager=config_manager,
            workspace=DirectoryWorkspace(
                str(tmp_path), include_markdown=False
            ),
            mode=mode,
            development_mode=False,
            quiet=True,
            cli_args={},
            argv=[],
        )

    uvicorn_config = server.call_args.args[0]
    app = uvicorn_config.app
    session_manager = app.state.session_manager
    assert {
        "port": uvicorn_config.port,
        "host": uvicorn_config.host,
        "external_host": app.state.host,
        "external_port": app.state.port,
        "base_url": app.state.base_url,
        "headless": app.state.headless,
        "skew_protection": app.state.skew_protection,
        "include_code": session_manager.include_code,
        "ttl_seconds": session_manager.ttl_seconds,
        "redirect_console_to_browser": session_manager.redirect_console_to_browser,
        "token_enabled": bool(session_manager.auth_token),
    } == {
        "port": 3210,
        "host": "127.0.0.1",
        "external_host": "marimo.example",
        "external_port": 443,
        "base_url": "/prefix",
        "headless": True,
        "skew_protection": False,
        "include_code": mode == SessionMode.EDIT,
        "ttl_seconds": None,
        "redirect_console_to_browser": False,
        "token_enabled": False,
    }
