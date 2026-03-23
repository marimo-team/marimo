# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class CliTip:
    text: str
    command: str | None = None
    link: str | None = None


@dataclass(frozen=True)
class StartupTipContext:
    command_path: tuple[str, ...]
    active_flags: frozenset[str]

    @classmethod
    def from_argv(cls, argv: Sequence[str]) -> StartupTipContext:
        tokens = list(argv)
        if "--" in tokens:
            tokens = tokens[: tokens.index("--")]
        return cls(
            command_path=_extract_command_path(_drop_leading_flags(tokens)),
            active_flags=frozenset(
                _normalize_flag(token)
                for token in tokens
                if token.startswith("-")
            ),
        )


@dataclass(frozen=True)
class _TipCommandSignature:
    command_path: tuple[str, ...]
    required_flags: frozenset[str]


def get_relevant_startup_tips(
    tips: tuple[CliTip, ...],
    context: StartupTipContext,
) -> tuple[CliTip, ...]:
    relevant = tuple(
        tip for tip in tips if _is_relevant_startup_tip(tip, context)
    )

    # If nothing matches, still show a tip instead of showing nothing.
    return relevant or tips


def _is_relevant_startup_tip(
    tip: CliTip,
    context: StartupTipContext,
) -> bool:
    signature = _get_tip_command_signature(tip)
    # Tips without commands, or runs we could not read cleanly, stay eligible.
    if signature is None or not context.command_path:
        return True

    # If the tip is about a different command, it is still useful.
    if signature.command_path != context.command_path:
        return True

    # If the tip needs flags the user already has on, it is redundant.
    return not signature.required_flags.issubset(context.active_flags)


def _get_tip_command_signature(tip: CliTip) -> _TipCommandSignature | None:
    if tip.command is None:
        return None

    # Read the example command once and use it
    # to decide when the tip is too close to what the user is already doing.
    try:
        tokens = shlex.split(tip.command)
    except ValueError:
        return None
    if tokens and tokens[0] == "marimo":
        tokens = tokens[1:]

    return _TipCommandSignature(
        command_path=_extract_command_path(tokens),
        required_flags=frozenset(
            _normalize_flag(token) for token in tokens if token.startswith("-")
        ),
    )


def _extract_command_path(tokens: Sequence[str]) -> tuple[str, ...]:
    command_path: list[str] = []
    for token in tokens:
        if token.startswith("-"):
            break

        if command_path and _looks_like_example_operand(token):
            break
        command_path.append(token)
    return tuple(command_path)


def _looks_like_example_operand(token: str) -> bool:
    return (
        token in {".", "..", "-"}
        or "://" in token
        or "/" in token
        or token.endswith(
            (
                ".py",
                ".ipynb",
                ".html",
                ".pdf",
                ".md",
                ".txt",
                ".csv",
                ".json",
                ".toml",
            )
        )
    )


def _drop_leading_flags(tokens: Sequence[str]) -> Sequence[str]:
    index = 0
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 1
    return tokens[index:]


def _normalize_flag(token: str) -> str:
    return token.split("=", 1)[0]


CLI_STARTUP_TIPS: Final[tuple[CliTip, ...]] = (
    CliTip(
        text="Run a notebook as a web app",
        command="marimo run notebook.py",
    ),
    CliTip(
        text="Watch for external edits and auto-reload",
        command="marimo edit notebook.py --watch",
    ),
    CliTip(
        text="Run a notebook in an isolated environment",
        command="marimo edit --sandbox notebook.py",
    ),
    CliTip(
        text="Open the intro tutorial",
        command="marimo tutorial intro",
    ),
    CliTip(
        text="Convert a Jupyter notebook",
        command="marimo convert notebook.ipynb -o notebook.py",
    ),
    CliTip(
        text="Install shell completions",
        command="marimo shell-completion",
    ),
    CliTip(
        text="Lint and format notebooks",
        command="marimo check --fix .",
    ),
    CliTip(
        text="Generate thumbnails for a folder",
        command="marimo export thumbnail folder/",
    ),
    CliTip(
        text="Coming from Jupyter?",
        link="https://docs.marimo.io/guides/coming_from/jupyter/",
    ),
)
