# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import click

from marimo._cli.help_formatter import ColoredCommand, ColoredGroup

SKILL_NAME = "marimo-pair"
SKILL_FILE = "SKILL.md"


@dataclass(frozen=True)
class AgentConfig:
    name: str
    skill_dirs: list[Path] = field(default_factory=list)

    def has_skill(self) -> bool:
        return any(
            (d / SKILL_NAME / SKILL_FILE).exists() for d in self.skill_dirs
        )


def _claude_skill_dirs() -> list[Path]:
    """Return all directories where a Claude Code skill may be installed.

    Skills can live under skills/, plugins/, or plugins/marketplaces/ in
    both the global (~/.claude) and local (.claude) config directories.
    """
    roots = [Path.home() / ".claude", Path.cwd() / ".claude"]
    subdirs = ["skills", "plugins", str(Path("plugins") / "marketplaces")]
    return [root / sub for root in roots for sub in subdirs]


AGENTS: dict[str, AgentConfig] = {
    "claude": AgentConfig(
        name="Claude Code",
        skill_dirs=_claude_skill_dirs(),
    ),
    "codex": AgentConfig(
        name="Codex",
        skill_dirs=[
            Path.home() / ".codex" / "skills",
            Path.cwd() / ".codex" / "skills",
        ],
    ),
    "opencode": AgentConfig(
        name="opencode",
        skill_dirs=[
            Path.home() / ".config" / "opencode" / "skills",
            Path.cwd() / ".config" / "opencode" / "skills",
        ],
    ),
}


@click.group(
    cls=ColoredGroup,
    help="""Commands for pair programming with AI.""",
)
def pair() -> None:
    pass


@click.command(
    cls=ColoredCommand,
    help="""Generate a prompt for pair programming on a running marimo notebook.""",
)
@click.option(
    "--url",
    required=True,
    type=str,
    help="URL of the running marimo kernel.",
)
@click.option(
    "--claude",
    is_flag=True,
    default=False,
    help="Validate that the marimo-pair Claude Code skill is installed.",
)
@click.option(
    "--codex",
    is_flag=True,
    default=False,
    help="Validate that the marimo-pair Codex skill is installed.",
)
@click.option(
    "--opencode",
    is_flag=True,
    default=False,
    help="Validate that the marimo-pair opencode skill is installed.",
)
def prompt(url: str, claude: bool, codex: bool, opencode: bool) -> None:
    """
    Generate a prompt for pair programming.

    Example usage:

        claude $(marimo pair prompt --url 'https://localhost:8000?auth=...' --claude)
        codex $(marimo pair prompt --url 'https://localhost:8000?auth=...' --codex)
        opencode $(marimo pair prompt --url 'https://localhost:8000?auth=...' --opencode)
    """
    selected_agents = {
        "claude": claude,
        "codex": codex,
        "opencode": opencode,
    }
    for key, agent in AGENTS.items():
        if not selected_agents[key]:
            continue
        if not agent.has_skill():
            click.echo(
                f"The marimo-pair skill for {agent.name} is not installed.\n\n"
                "Let the user know they need to install it with:\n\n"
                "  npx skills add marimo-team/marimo-pair\n\n"
                "or\n\n"
                "  uvx deno -A npm:skills add marimo-team/marimo-pair\n\n"
                "More instructions at "
                "https://github.com/marimo-team/marimo-pair",
                err=True,
            )
            sys.exit(1)

    click.echo(
        "Use the /marimo-pair skill to pair-program on a running "
        "marimo notebook.\n\n"
        f"Connect to the notebook at: {url}\n\n"
        f"Use `execute-code.sh --url {url}` from the marimo-pair "
        "skill to execute code in the notebook. \n\n"
        "Once you are connected, send a fun toast to the user inside marimo letting them know you're ready to pair."
    )


pair.add_command(prompt)
