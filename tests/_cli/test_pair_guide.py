# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path

from marimo._cli.pair.client import PairServer, ResolvedTarget, SessionInfo
from marimo._cli.pair.guide import (
    render_cli_guide,
    render_code_mode_guide,
)
from marimo._server.ai.skills import utils as skill_utils


def test_execution_adapters_own_bridge_instructions() -> None:
    code_mode = skill_utils.load_adapter("code-mode")
    cli = skill_utils.load_adapter("cli")
    canonical = skill_utils.load_skill("marimo-pair")

    assert "execute_code" in code_mode
    assert "marimo pair execute" in cli
    assert len(code_mode.splitlines()) <= 25
    assert len(cli.splitlines()) <= 25

    for executor_detail in (
        "execute-code.sh",
        "execute_code",
        "/api/",
        "curl",
        "jq",
        "frontend command",
    ):
        assert executor_detail not in canonical
    assert len(canonical.splitlines()) <= 277


def test_canonical_guide_preserves_first_command_contract() -> None:
    canonical = skill_utils.load_skill("marimo-pair")

    assert "## Required First Kernel Command" in canonical
    assert "import marimo._code_mode as cm\nhelp(cm)" in canonical
    assert "Run only the inspection command above" in canonical
    assert "before the inspection succeeds" in canonical


def test_code_mode_guide_prepends_native_adapter() -> None:
    rendered = render_code_mode_guide()

    assert rendered == (
        f"{skill_utils.load_adapter('code-mode').rstrip()}\n\n"
        f"{skill_utils.load_skill('marimo-pair').rstrip()}\n"
    )


def test_cli_guide_renders_resumable_target_command() -> None:
    target = ResolvedTarget(
        server=PairServer(
            server_id="example.com:443",
            origin="direct",
            url="https://example.com",
            started_at="",
            version="0.24.1",
        ),
        session=SessionInfo(
            session_id="s_one",
            filename="analysis.py",
            path="/work/analysis.py",
        ),
        version="0.24.1",
    )

    rendered = render_cli_guide(
        target,
        token_file=Path("token.txt"),
        token_from_environment=False,
    )

    assert "Server: `https://example.com`" in rendered
    assert "Session: `s_one`" in rendered
    assert "Notebook key: `/work/analysis.py`" in rendered
    assert "marimo version: `0.24.1`" in rendered
    assert "Token source: `--token-file token.txt`" in rendered
    assert (
        "uvx --from marimo==0.24.1 marimo pair execute "
        "--url https://example.com --session s_one --token-file token.txt"
        in rendered
    )
    assert "import marimo._code_mode as cm\nhelp(cm)" in rendered


def test_cli_guide_names_environment_without_exposing_token() -> None:
    target = ResolvedTarget(
        server=PairServer(
            server_id="localhost:2718",
            origin="local",
            url="http://localhost:2718",
            started_at="",
            version="0.24.1",
        ),
        session=SessionInfo(
            session_id="s_two",
            filename="notebook.py",
            path=None,
        ),
        version="0.24.1",
    )

    rendered = render_cli_guide(
        target,
        token_file=None,
        token_from_environment=True,
    )

    assert "Notebook key: `notebook.py`" in rendered
    assert "Token source: `MARIMO_TOKEN`" in rendered
    assert "--token-file" not in rendered
