# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

import click

from marimo._cli.help_formatter import ColoredCommand, ColoredGroup

SKILL_NAME = "marimo-pair"
SKILL_FILE = "SKILL.md"


_cached_token_dir: Path | None = None


def _token_dir() -> Path:
    import tempfile

    global _cached_token_dir
    if _cached_token_dir is None:
        _cached_token_dir = Path(tempfile.mkdtemp(prefix="marimo-pair-"))
    return _cached_token_dir


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
@click.option(
    "--with-token",
    is_flag=True,
    default=False,
    help="Prompt for an auth token and store it in a temp file.",
)
def prompt(
    url: str,
    claude: bool,
    codex: bool,
    opencode: bool,
    with_token: bool,
) -> None:
    """
    Generate a prompt for pair programming.

    Example usage:

        claude "$(uvx marimo@latest pair prompt --url 'https://localhost:8000' --claude)"
        codex "$(uvx marimo@latest pair prompt --url 'https://localhost:8000' --codex)"
        opencode "$(uvx marimo@latest pair prompt --url 'https://localhost:8000' --opencode)"

        # With an auth token
        claude "$(uvx marimo@latest pair prompt --url 'https://localhost:8000' --claude --with-token)"
    """
    # Validate that the selected agents have the required skills
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
                f"The marimo-pair skill for {agent.name} could not be found.\n\n"
                "Please install it with:\n\n"
                "  npx skills add marimo-team/marimo-pair\n\n"
                "or\n\n"
                "  uvx deno -A npm:skills add marimo-team/marimo-pair\n\n"
                "More instructions at "
                "https://github.com/marimo-team/marimo-pair",
                err=True,
            )

    # Prompt for token and write it to a temp file if --with-token is set
    token_hint = ""
    if with_token:
        token_dir = _token_dir()
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:6]
        token_file = token_dir / f"{url_hash}-token.txt"
        token = click.prompt("Auth token", hide_input=True, err=True)
        token_dir.mkdir(parents=True, exist_ok=True)
        # Open the token file for writing, creating it with restrictive
        # permissions if needed and truncating it if it already exists.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(token_file, flags, 0o600)
        try:
            os.write(fd, token.encode())
        finally:
            os.close(fd)

        token_hint = (
            f"\n\nAn auth token is stored at {token_file}. "
            f"Pass it via `execute-code.sh --url '{url}' "
            f"--token \"$(cat '{token_file}')\"`."
        )

    # Output the prompt to the wrapper agent CLI
    click.echo(
        "Use the /marimo-pair skill to pair-program on a running "
        "marimo notebook.\n\n"
        f"Connect to the notebook at: {url}\n\n"
        f"Use `execute-code.sh --url {url}` from the marimo-pair "
        "skill to execute code in the notebook."
        f"{token_hint}\n\n"
        "Once you are connected, send a fun toast to the user inside marimo letting them know you're ready to pair."
    )


pair.add_command(prompt)
