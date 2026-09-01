# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import json
import os
import shlex
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import click

from marimo._cli.help_formatter import ColoredCommand, ColoredGroup
from marimo._cli.pair.client import PairError, PairServer
from marimo._cli.pair.discovery import discover_servers

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

    Skills can be installed directly or bundled in a marketplace plugin in
    both the global (`~/.claude`) and local (`.claude`) config directories.
    """
    roots = [Path.home() / ".claude", Path.cwd() / ".claude"]
    subdirs = ["skills", "plugins", str(Path("plugins") / "marketplaces")]
    return [
        *[root / sub for root in roots for sub in subdirs],
        *[
            skill_dir
            for root in roots
            for skill_dir in _plugin_skill_dirs(root)
        ],
    ]


def _plugin_skill_dirs(root: Path) -> list[Path]:
    """Return skill directories from marketplace and cached plugins."""
    plugins = root / "plugins"
    return [
        *plugins.glob("marketplaces/*/skills"),
        *plugins.glob(f"cache/*/{SKILL_NAME}/*/skills"),
    ]


def _codex_skill_dirs() -> list[Path]:
    """Return directories where a Codex skill may be installed."""
    roots = [Path.home() / ".codex", Path.cwd() / ".codex"]
    return [
        *[root / "skills" for root in roots],
        *[
            skill_dir
            for root in roots
            for skill_dir in _plugin_skill_dirs(root)
        ],
    ]


def _opencode_skill_dirs() -> list[Path]:
    """Return directories where an opencode skill (or compatible layout) may live.

    https://opencode.ai/docs/skills/
    Checked roots are the parent of `<skill-name>/SKILL.md` for:

    - Project opencode: `.opencode/skills/`
    - Global opencode: `~/.config/opencode/skills/`
    - Project Claude-compatible: `.claude/skills/`
    - Global Claude-compatible: `~/.claude/skills/`
    - Project agent-compatible: `.agents/skills/`
    - Global agent-compatible: `~/.agents/skills/`
    """
    cwd = Path.cwd()
    home = Path.home()
    return [
        cwd / ".opencode" / "skills",
        home / ".config" / "opencode" / "skills",
        cwd / ".claude" / "skills",
        home / ".claude" / "skills",
        cwd / ".agents" / "skills",
        home / ".agents" / "skills",
    ]


def pair_agents() -> dict[str, AgentConfig]:
    """Return agent configs; paths use `Path.cwd()` at call time."""
    return {
        "claude": AgentConfig(
            name="Claude Code",
            skill_dirs=_claude_skill_dirs(),
        ),
        "codex": AgentConfig(
            name="Codex",
            skill_dirs=_codex_skill_dirs(),
        ),
        "opencode": AgentConfig(
            name="opencode",
            skill_dirs=_opencode_skill_dirs(),
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
    "--file",
    "file_path",
    default=None,
    type=str,
    help="Notebook path or file key from the page URL.",
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
    file_path: str | None,
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

        # Connect to a specific notebook
        claude "$(uvx marimo@latest pair prompt --url 'https://localhost:8000' --file 'notebooks/example.py' --claude)"

        # With an auth token
        claude "$(uvx marimo@latest pair prompt --url 'https://localhost:8000' --claude --with-token)"
    """
    # Preserve the file key exactly as supplied. Relative keys are resolved by
    # the server workspace and may refer to a remote or non-POSIX filesystem.
    # Shell-quote dynamic values because this command is copy-pasted into a
    # shell and paths may contain spaces or metacharacters.
    file_flag = f" --file {shlex.quote(file_path)}" if file_path else ""
    execute_cmd = f"execute-code.sh --url {shlex.quote(url)}{file_flag}"
    # Validate that the selected agents have the required skills
    selected_agents = {
        "claude": claude,
        "codex": codex,
        "opencode": opencode,
    }
    for key, agent in pair_agents().items():
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
            f"Pass it via `{execute_cmd} "
            f"--token \"$(cat '{token_file}')\"`."
        )

    file_hint = f" (file {file_path})" if file_path else ""

    # Output the prompt to the wrapper agent CLI
    click.echo(
        "Use the /marimo-pair skill to pair-program on a running "
        "marimo notebook.\n\n"
        f"Connect to the notebook at: {url}{file_hint}\n\n"
        f"Use `{execute_cmd}` from the marimo-pair "
        "skill to execute code in the notebook."
        f"{token_hint}\n\n"
        "Once you are connected, send a fun toast (mo.status.toast(...)) to the user inside marimo letting them know you're ready to pair."
    )


def _redact_url(url: str | None) -> str | None:
    if url is None:
        return None
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    netloc = f"{host}:{parsed.port}" if parsed.port is not None else host
    query = urlencode(
        tuple(
            (key, "REDACTED")
            for key, _value in parse_qsl(parsed.query, keep_blank_values=True)
        )
    )
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path, query, parsed.fragment)
    )


def _redact_server(server: PairServer) -> PairServer:
    return replace(server, url=_redact_url(server.url))


def _render_discovery_json(servers: tuple[PairServer, ...]) -> None:
    click.echo(json.dumps([asdict(server) for server in servers], indent=2))


def _render_discovery_text(servers: tuple[PairServer, ...]) -> None:
    for server in servers:
        click.echo(
            "\t".join(
                (
                    server.server_id,
                    server.origin,
                    server.url or "",
                    server.version,
                    server.started_at,
                )
            )
        )


def _render_pair_error(error: PairError, *, json_errors: bool) -> None:
    if json_errors:
        click.echo(
            json.dumps({"kind": error.kind, "message": error.message}),
            err=True,
        )
    else:
        click.echo(f"Error: {error.message}", err=True)


@click.command(
    cls=ColoredCommand,
    help="Discover running marimo servers.",
)
@click.option(
    "--format",
    "output_format",
    default="text",
    type=click.Choice(["text", "json"], case_sensitive=False),
    show_default=True,
    help="Output format.",
)
@click.option(
    "--json-errors",
    is_flag=True,
    default=False,
    help="Write machine-readable errors to stderr.",
)
def discover(output_format: str, json_errors: bool) -> None:
    try:
        result = discover_servers()
    except PairError as error:
        _render_pair_error(error, json_errors=json_errors)
        raise click.exceptions.Exit(1) from None
    servers = tuple(_redact_server(server) for server in result.servers)
    if output_format == "json":
        _render_discovery_json(servers)
    else:
        _render_discovery_text(servers)
    for warning in result.warnings:
        click.echo(warning, err=True)


pair.add_command(discover)
pair.add_command(prompt)
