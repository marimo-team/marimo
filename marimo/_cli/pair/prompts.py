# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from marimo._utils.parse_dataclass import parse_raw

PAIR_COMMAND = "uvx marimo@latest"


@dataclass(frozen=True)
class PromptTemplates:
    prompt: str
    file: str
    session: str
    token_file: str
    token: str


def load_prompt_templates() -> PromptTemplates:
    return parse_raw(
        Path(__file__).with_name("prompt.json").read_text(encoding="utf-8"),
        PromptTemplates,
    )


def render_prompt(
    *,
    url: str,
    file_path: str | None = None,
    session_id: str | None = None,
    token_file: Path | None = None,
) -> str:
    templates = load_prompt_templates()
    return templates.prompt.format(
        command=PAIR_COMMAND,
        url=url,
        file=templates.file.format(file=file_path) if file_path else "",
        session=(
            templates.session.format(session=session_id) if session_id else ""
        ),
        authentication=(
            templates.token_file.format(
                token_file=shlex.quote(str(token_file))
            )
            if token_file is not None
            else ""
        ),
    )
