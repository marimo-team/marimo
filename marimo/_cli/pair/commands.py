# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

import click
from click.utils import get_text_stream

from marimo._cli.help_formatter import ColoredCommand, ColoredGroup
from marimo._cli.pair.client import (
    PairError,
    execute as execute_code,
    load_token,
)
from marimo._server.ai.skills import utils as skills_utils

SKILL_NAME = "marimo-pair"
SKILL_FILE = "SKILL.md"
_REFERENCES_DIR = (
    Path(skills_utils.__file__).parent / "marimo-pair" / "references"
)


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


def _doc_topics() -> dict[str, str]:
    return {
        path.stem: path.read_text(encoding="utf-8")
        .splitlines()[0]
        .removeprefix("# ")
        for path in sorted(_REFERENCES_DIR.glob("*.md"))
    }


class _DocsCommand(ColoredCommand):
    def format_epilog(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        del ctx
        formatter.write_paragraph()
        formatter.write_text("Available topics:")
        with formatter.indentation():
            formatter.write_dl(list(_doc_topics().items()))


@click.group(
    cls=ColoredGroup,
    help="""Pair with a live marimo notebook.

    Read a command's --help before first use.
    """,
)
def pair() -> None:
    pass


@click.command(
    cls=ColoredCommand,
    help="""Run Python in the selected live notebook kernel's scratchpad.""",
    epilog="""\b
If you have not already inspected cm in this kernel, execute this call
by itself before task-specific code:
  import marimo._code_mode as cm
  help(cm)

The live kernel is the source of truth for state and available cm APIs.
Scratchpad bindings are temporary. Make durable notebook edits through cm.
Import cm in the scratchpad, not into a notebook cell.

If a session is stale, rediscover it. Never silently switch sessions.
Ctrl-C closes the request; the server interrupts the session kernel.
If the connection ends before completion is confirmed, do not retry
execution automatically. Inspect notebook state before deciding what to do.

\b
For name-redefinition traps: marimo pair docs gotchas
For custom visual output: marimo pair docs rich-representations
For notebook cleanup: marimo pair docs notebook-improvements

\b
First inspection template:
  uv run marimo pair execute --url '<server-url>' --session '<session-id>' --token-file '<token-file>' -c 'import marimo._code_mode as cm; help(cm)'
""",
)
@click.option(
    "--url",
    required=True,
    metavar="URL",
    help="Server URL.",
)
@click.option(
    "--session",
    "session_id",
    required=True,
    metavar="ID",
    help="Current session ID. Required on every execution.",
)
@click.option(
    "--token-file",
    type=click.Path(path_type=Path, dir_okay=False),
    metavar="PATH",
    help="Read the server token from a local file. Otherwise use MARIMO_TOKEN, if set.",
)
@click.option(
    "-c",
    "code",
    help="Inline Python.",
)
@click.option(
    "--code-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    metavar="PATH",
    help="Read Python from a UTF-8 file. Supply exactly one input option. No implicit stdin input.",
)
@click.option(
    "--no-stream",
    is_flag=True,
    help="Buffer output until execution ends. Default: stream stdout and stderr as they arrive.",
)
@click.pass_context
def execute(
    ctx: click.Context,
    url: str,
    session_id: str,
    token_file: Path | None,
    code: str | None,
    code_file: Path | None,
    no_stream: bool,
) -> None:
    if (code is None) == (code_file is None):
        raise click.UsageError("Specify -c or --code-file.")

    if code_file is not None:
        try:
            code = code_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise click.UsageError("Could not read the code file.") from error
    assert code is not None
    if not code:
        raise click.UsageError("Code must not be empty.")

    try:
        token = load_token(token_file, os.environ)
        result = execute_code(
            url=url,
            session_id=session_id,
            token=token,
            code=code,
            stdout=get_text_stream("stdout"),
            stderr=get_text_stream("stderr"),
            stream=not no_stream,
        )
    except PairError as error:
        click.echo(str(error), err=True)
        ctx.exit(1)
    except KeyboardInterrupt:
        click.echo("Interrupted.", err=True)
        ctx.exit(1)

    if not result.success:
        ctx.exit(1)


@click.command(
    cls=_DocsCommand,
    help="Read notebook guidance on demand.",
)
@click.argument("topic", required=False)
def docs(topic: str | None) -> None:
    topics = _doc_topics()
    if topic is None:
        for name, title in topics.items():
            click.echo(f"{name}  {title}")
        return

    if topic not in topics:
        valid_topics = ", ".join(topics)
        raise click.UsageError(
            f"Unknown topic {topic!r}. Valid topics: {valid_topics}."
        )

    click.echo(
        (_REFERENCES_DIR / f"{topic}.md").read_text(encoding="utf-8"),
        nl=False,
    )


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
    "--session",
    "session_id",
    required=True,
    type=str,
    help="Current session ID.",
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
    "--uv-project",
    is_flag=True,
    default=False,
    help="Use the current uv project in generated marimo commands.",
)
@click.option(
    "--with-token",
    is_flag=True,
    default=False,
    help="Prompt for an auth token and store it in a temp file.",
)
def prompt(
    url: str,
    session_id: str,
    file_path: str | None,
    claude: bool,
    codex: bool,
    opencode: bool,
    uv_project: bool,
    with_token: bool,
) -> None:
    """
    Generate a prompt for pair programming.

    Example usage:

        claude "$(uv run marimo pair prompt --url 'https://localhost:8000' --session 'session-123' --claude)"
        codex "$(uv run marimo pair prompt --url 'https://localhost:8000' --session 'session-123' --codex)"
        opencode "$(uv run marimo pair prompt --url 'https://localhost:8000' --session 'session-123' --opencode)"

        # Connect to a specific notebook
        claude "$(uv run marimo pair prompt --url 'https://localhost:8000' --session 'session-123' --file 'notebooks/example.py' --claude)"

        # With an auth token
        claude "$(uv run marimo pair prompt --url 'https://localhost:8000' --session 'session-123' --claude --with-token)"
    """
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
    token_file: Path | None = None
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

    target_lines = [
        "Pair with the live marimo notebook at this target:",
        f"  Server: {url}",
        f"  Session: {session_id}",
    ]
    if file_path:
        target_lines.append(f"  Notebook: {file_path}")
    if token_file:
        target_lines.append(f"  Token file: {token_file}")

    # Output the prompt to the wrapper agent CLI
    click.echo(
        "\n".join(target_lines) + "\n\n"
        f"Start with: {'uv run marimo' if uv_project else 'uvx marimo@latest'} "
        "pair --help\n\n"
        "Once you are connected, send a fun toast (mo.status.toast(...)) to the user inside marimo letting them know you're ready to pair."
    )


pair.add_command(execute)
pair.add_command(docs)
pair.add_command(prompt)
