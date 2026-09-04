# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._server.ai.skills.utils import load_adapter, load_skill
from marimo._utils.strings import cmd_quote

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._cli.pair.client import ResolvedTarget


def render_code_mode_guide() -> str:
    """Render the native bridge and the canonical notebook workflow."""
    return (
        f"{load_adapter('code-mode').rstrip()}\n\n"
        f"{load_skill('marimo-pair').rstrip()}\n"
    )


def render_cli_guide(
    target: ResolvedTarget,
    *,
    token_file: Path | None,
    token_from_environment: bool,
) -> str:
    """Render the CLI bridge and the canonical notebook workflow."""
    url = target.server.url
    if url is None:
        raise ValueError("The resolved pair target is not reachable.")

    command_parts = [
        "uvx",
        "--from",
        f"marimo=={target.version}",
        "marimo",
        "pair",
        "execute",
        "--url",
        url,
        "--session",
        target.session.session_id,
    ]
    if token_file is not None:
        command_parts.extend(("--token-file", str(token_file)))

    notebook_key = (
        target.session.path or target.session.filename or "(not available)"
    )
    if token_file is not None:
        token_source = f"--token-file {token_file}"
    elif token_from_environment:
        token_source = "MARIMO_TOKEN"
    else:
        token_source = "none"

    adapter = load_adapter("cli")
    replacements = {
        "{server_url}": url,
        "{session_id}": target.session.session_id,
        "{notebook_key}": notebook_key,
        "{version}": target.version,
        "{token_source}": token_source,
        "{execute_command}": " ".join(map(cmd_quote, command_parts)),
    }
    for marker, value in replacements.items():
        adapter = adapter.replace(marker, value)

    return f"{adapter.rstrip()}\n\n{load_skill('marimo-pair').rstrip()}\n"
