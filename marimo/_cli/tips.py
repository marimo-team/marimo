# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import random
import shlex
import sys
from dataclasses import dataclass
from typing import Final

import click
from click.core import ParameterSource


@dataclass(frozen=True)
class CliTip:
    text: str
    command: str | None = None
    link: str | None = None


CLI_STARTUP_TIPS: Final[tuple[CliTip, ...]] = (
    CliTip(
        text="Run a notebook as a web app",
        command="marimo run notebook.py",
    ),
    CliTip(
        text="Reload the editor when the notebook file is edited externally",
        command="marimo edit notebook.py --watch",
    ),
    CliTip(
        text="Run a notebook in an isolated virtual environment",
        command="marimo edit --sandbox notebook.py",
    ),
    CliTip(
        text="Open the intro tutorial",
        command="marimo tutorial intro",
    ),
    CliTip(
        text="Convert a Jupyter notebook to a marimo notebook",
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
        text="Pair-program with AI agents on running notebooks",
        link="https://links.marimo.app/marimo-pair",
    ),
    CliTip(
        text="Coming from Jupyter?",
        link="https://docs.marimo.io/guides/coming_from/jupyter/",
    ),
)


@dataclass(frozen=True)
class InvocationSignature:
    command_path: tuple[str, ...]
    enabled_options: frozenset[str]


def choose_startup_tip(
    ctx: click.Context,
    tips: tuple[CliTip, ...] | None = None,
) -> CliTip | None:
    if not sys.stdout.isatty():
        return None

    tips = tips or CLI_STARTUP_TIPS
    current = signature_from_click_context(ctx)
    root = ctx.find_root().command
    if not isinstance(root, click.Group):
        return random.choice(tips)
    relevant = get_relevant_startup_tips(
        tips=tips,
        current=current,
        root=root,
    )
    return random.choice(relevant)


def get_relevant_startup_tips(
    tips: tuple[CliTip, ...],
    current: InvocationSignature,
    root: click.Group,
) -> tuple[CliTip, ...]:
    relevant = tuple(
        tip for tip in tips if _is_relevant_startup_tip(tip, current, root)
    )

    # If nothing matches, still show a tip instead of showing nothing.
    return relevant or tips


def signature_from_click_context(ctx: click.Context) -> InvocationSignature:
    contexts = _context_chain(ctx)
    command_path = tuple(
        _context_command_name(context) for context in contexts[1:]
    )
    enabled_options = frozenset(
        option_name
        for context in contexts
        for option_name in _explicitly_set_option_names(context)
    )
    return InvocationSignature(
        command_path=command_path,
        enabled_options=enabled_options,
    )


def signature_from_command_example(
    root: click.Group,
    command: str,
) -> InvocationSignature | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None

    if tokens and tokens[0] == "marimo":
        tokens = tokens[1:]

    if not tokens:
        return None

    try:
        root_ctx = root.make_context(
            "marimo",
            list(tokens),
            resilient_parsing=True,
        )
        cmd_name, cmd, args = root.resolve_command(root_ctx, list(tokens))
        if cmd is None:
            return None
        sub_ctx = cmd.make_context(
            cmd_name,
            args,
            parent=root_ctx,
            resilient_parsing=True,
        )
    except click.ClickException:
        return None
    except Exception:
        return None

    return signature_from_click_context(sub_ctx)


def _is_relevant_startup_tip(
    tip: CliTip,
    current: InvocationSignature,
    root: click.Group,
) -> bool:
    if tip.command is None:
        return True

    tip_signature = signature_from_command_example(root, tip.command)
    if tip_signature is None:
        return True

    if tip_signature.command_path != current.command_path:
        return True

    return not tip_signature.enabled_options.issubset(current.enabled_options)


def _context_chain(ctx: click.Context) -> list[click.Context]:
    chain: list[click.Context] = []
    current: click.Context | None = ctx
    while current is not None:
        chain.append(current)
        current = current.parent
    return list(reversed(chain))


def _context_command_name(ctx: click.Context) -> str:
    return ctx.command.name or ctx.info_name or ""


def _explicitly_set_option_names(ctx: click.Context) -> list[str]:
    options: list[str] = []
    for param in ctx.command.params:
        if not isinstance(param, click.Option):
            continue
        if param.name is None:
            continue
        source = ctx.get_parameter_source(param.name)
        if source is None or source == ParameterSource.DEFAULT:
            continue
        value = ctx.params.get(param.name)
        if isinstance(value, bool) and not value:
            continue
        options.append(param.name)
    return options
