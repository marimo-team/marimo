# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from marimo._utils.parse_dataclass import parse_raw


@dataclass(frozen=True)
class PromptTemplates:
    prompt: str
    notebook: str
    session: str
    token_file: str
    token: str


def load_prompt_templates() -> PromptTemplates:
    return parse_raw(
        Path(__file__).with_name("prompt.json").read_text(encoding="utf-8"),
        PromptTemplates,
    )


def get_marimo_command() -> str:
    """Use the running installation without requiring an activated environment."""
    return f"{shlex.quote(sys.executable)} -m marimo"


def render_prompt(
    *,
    url: str,
    notebook_id: str | None = None,
    session_id: str | None = None,
    token_file: Path | None = None,
) -> str:
    templates = load_prompt_templates()
    return templates.prompt.format(
        command=get_marimo_command(),
        url=url,
        notebook=(
            templates.notebook.format(notebook=notebook_id)
            if notebook_id
            else ""
        ),
        session=templates.session.format(session=session_id)
        if session_id and not notebook_id
        else "",
        authentication=(
            templates.token_file.format(
                token_file=shlex.quote(str(token_file))
            )
            if token_file is not None
            else ""
        ),
    )
