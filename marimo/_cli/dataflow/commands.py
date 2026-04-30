# Copyright 2026 Marimo. All rights reserved.
"""``marimo dataflow`` CLI subcommands.

These commands surface assets that ship inside the marimo wheel — the
TypeScript client and the agent skill — so any environment with
``marimo`` installed can vendor them without a separate download:

    marimo dataflow client        > src/dataflow.tsx
    marimo dataflow client --path             # filesystem path to dataflow.tsx
    marimo dataflow skill         > SKILL.md
    marimo dataflow skill  --path             # repo root for ``gh skill install``

``skill --path`` returns the *root* that satisfies the agent-skills layout
(``<root>/skills/<name>/SKILL.md``), so it composes directly with the
GitHub CLI:

    gh skill install --from-local "$(marimo dataflow skill --path)" dataflow --agent claude-code

The TypeScript file ships at ``marimo/_dataflow/clients/typescript/`` and
the skill at ``marimo/_dataflow/skills/dataflow/SKILL.md``; both are
bundled by the uv build backend along with the rest of the ``marimo``
module.
"""

from __future__ import annotations

import click

from marimo._cli.help_formatter import ColoredCommand, ColoredGroup
from marimo._utils.paths import marimo_package_path

_CLIENT_PATH = ("_dataflow", "clients", "typescript", "dataflow.tsx")
# Root that satisfies the agent-skills ``<root>/skills/<name>/SKILL.md``
# layout, so it composes with ``gh skill install --from-local <root> <name>``.
_SKILL_ROOT_PATH = ("_dataflow",)
_SKILL_NAME = "dataflow"
_SKILL_FILE = "SKILL.md"


def _resolve(*parts: str) -> str:
    path = marimo_package_path()
    for part in parts:
        path = path / part
    return str(path)


@click.group(
    cls=ColoredGroup,
    help=(
        "Bundled assets for building dataflow API clients.\n\n"
        "The dataflow API exposes a marimo notebook as a typed reactive "
        "function over Server-Sent Events. These subcommands print the "
        "TypeScript client and the agent skill that ship inside the "
        "marimo wheel.\n\n"
        "Run ``marimo dataflow skill`` for an end-to-end recipe, or "
        "``gh skill install --from-local \"$(marimo dataflow skill --path)\"`` "
        "to register it with your local agent."
    ),
)
def dataflow() -> None:
    """Bundled dataflow client + agent skill assets."""


@dataflow.command(cls=ColoredCommand)
@click.option(
    "--path",
    "show_path",
    is_flag=True,
    help="Print the filesystem path of the bundled file instead of its contents.",
)
def client(show_path: bool) -> None:
    """Print the bundled TypeScript dataflow client (``dataflow.tsx``).

    Vendor it into your project:

        marimo dataflow client > src/dataflow.tsx
    """
    path = _resolve(*_CLIENT_PATH)
    if show_path:
        click.echo(path)
        return
    with open(path, encoding="utf-8") as f:
        click.echo(f.read(), nl=False)


@dataflow.command(cls=ColoredCommand)
@click.option(
    "--path",
    "show_path",
    is_flag=True,
    help=(
        "Print the agent-skills root path instead of the markdown. The "
        "returned directory contains ``skills/dataflow/SKILL.md``, so it "
        "feeds straight into ``gh skill install --from-local <path> dataflow``."
    ),
)
def skill(show_path: bool) -> None:
    """Print the bundled dataflow agent skill (``SKILL.md``).

    The skill follows the open Agent Skills spec and ships at
    ``marimo/_dataflow/skills/dataflow/SKILL.md`` inside the wheel.

    Install it with the GitHub CLI:

        gh skill install marimo-team/marimo dataflow --agent claude-code
        # or, without cloning the repo:
        gh skill install --from-local "$(marimo dataflow skill --path)" dataflow --agent claude-code

    Or pipe the markdown directly into your agent's skill folder.
    """
    root = _resolve(*_SKILL_ROOT_PATH)
    if show_path:
        click.echo(root)
        return
    with open(
        f"{root}/skills/{_SKILL_NAME}/{_SKILL_FILE}", encoding="utf-8"
    ) as f:
        click.echo(f.read(), nl=False)
