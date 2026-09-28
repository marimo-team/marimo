# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

import click

from marimo._cli.help_formatter import ColoredCommand, ColoredGroup
from marimo._cli.pair.client import (
    AmbiguousSessionError,
    NoSessionError,
    PairError,
    PairInputError,
    StaleSessionError,
    display_url,
    execute as execute_code,
    list_sessions,
    load_token,
    registry_urls,
    resolve_session,
)
from marimo._cli.pair.prompts import render_prompt
from marimo._server.ai.skills import utils as skills_utils
from marimo._utils.env import is_env_true

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
        for directory in self.skill_dirs:
            try:
                if (directory / SKILL_NAME / SKILL_FILE).exists():
                    return True
            except OSError:
                # Skill detection is advisory. An inaccessible directory must
                # not prevent marimo from generating the pairing prompt.
                continue
        return False


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
    """Return directories where a Codex skill may be installed.

    Codex loads repository skills from `.agents/skills` directories between
    the current directory and repository root. It also loads user and admin
    skills from `~/.agents/skills` and `/etc/codex/skills`, respectively.

    Keep checking `.codex` for existing direct and plugin installations.
    """
    cwd = Path.cwd()
    home = Path.home()
    roots = [home / ".codex", cwd / ".codex"]
    return [
        *_codex_repository_skill_dirs(cwd),
        home / ".agents" / "skills",
        Path("/etc/codex/skills"),
        *[root / "skills" for root in roots],
        *[
            skill_dir
            for root in roots
            for skill_dir in _plugin_skill_dirs(root)
        ],
    ]


def _codex_repository_skill_dirs(cwd: Path) -> list[Path]:
    """Return Codex skill directories from `cwd` through the repository root."""
    skill_dirs: list[Path] = []
    for directory in (cwd, *cwd.parents):
        skill_dirs.append(directory / ".agents" / "skills")
        try:
            is_repository_root = (directory / ".git").exists()
        except OSError:
            # Do not search above an ancestor whose repository status cannot
            # be determined. The global user and admin paths remain available.
            return skill_dirs
        if is_repository_root:
            return skill_dirs

    # Outside a Git repository, Codex still checks the current directory.
    return skill_dirs[:1]


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

    \b
    Authentication:
      If a token-file path is supplied, add --token-file <PATH> to every
      execute and notebook list command. Pass the path, not the file contents.
      Otherwise, these commands use MARIMO_TOKEN when set.

    \b
    Workflow:
      If you do not have the server URL or notebook file:
        marimo pair notebook list
      marimo pair execute --url <URL> --file <FILE> --code-file - <<'PY'
      import marimo._code_mode as cm
      async with cm.get_context() as ctx:
          ctx.packages.add("pandas")
          cid = ctx.create_cell("import pandas as pd")
          ctx.run_cell(cid)
      PY
      marimo pair execute --url <URL> --file <FILE> --code-file - <<'PY'
      import marimo._code_mode as cm
      async with cm.get_context() as ctx:
          cell = ctx.cells["<CELL_ID>"]
          print(cell.status, cell.errors, [o.data for o in cell.console_outputs])
      PY

    \b
    Target selection:
      If the notebook file is known, use --file <FILE> without --session.
      This resolves the notebook's current session after a page reload.
      If no file is known, use the supplied --session <SESSION>.
      If --file matches multiple sessions, use the supplied session for the intended notebook.
      If the intended session is unclear, run marimo pair notebook list again.
      Session IDs change when the page reloads. If execute reports a stale
      session, run marimo pair notebook list again.
      If both options are supplied, --session takes precedence over --file.
      Do not switch sessions after authentication or connection errors,
      or when execution is unconfirmed.

    \b
    Rules:
      Cells are the unit of work. The scratchpad is temporary; only code mode edits persist.
      Cells do not run on creation. Call run_cell after create_cell or edit_cell.
      Use async with. Do not await ctx methods.
      Install packages with ctx.packages.add, not uv add or pip. Installs change
      the project; confirm when the user did not ask.
      If an empty cell exists, edit_cell it instead of creating one.
      delete_cell drops the cell's variables. Ask before deleting.

    \b
    Code-mode API:
      Prefer marimo._code_mode to inspect, create, edit, run, and delete notebook cells.
      ctx.cells                 # each has .id .code .status .errors .console_outputs
      ctx.create_cell(code)     # returns the new cell id
      ctx.edit_cell(cid, code)
      ctx.run_cell(cid)
      ctx.delete_cell(cid)
      ctx.packages.add("pandas>=2")  # queued, installs on exit
      If a cm call fails, run help(cm):
        marimo pair execute --url <URL> --file <FILE> -c 'import marimo._code_mode as cm; help(cm)'
    """,
)
def pair() -> None:
    pass


@click.command(
    cls=ColoredCommand,
    help="""Run Python in the selected live notebook kernel's scratchpad.""",
    short_help="""Run Python in a live notebook session.""",
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
    required=False,
    metavar="ID",
    help="Current session ID. Resolved from --file when omitted.",
)
@click.option(
    "--file",
    "file_path",
    required=False,
    metavar="PATH",
    help="Notebook path or file key. Used to resolve --session when omitted.",
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
    metavar="PATH",
    help="Read Python from a UTF-8 file, or from stdin when PATH is '-'. Supply exactly one input option.",
)
@click.option(
    "--stream",
    "stream",
    is_flag=True,
    help="Write stdout and stderr as they arrive. Default: print one JSON result.",
)
@click.pass_context
def execute(
    ctx: click.Context,
    url: str,
    session_id: str | None,
    file_path: str | None,
    token_file: Path | None,
    code: str | None,
    code_file: str | None,
    stream: bool,
) -> None:
    if (code is None) == (code_file is None):
        raise click.UsageError("Specify -c or --code-file.")

    if code_file == "-":
        code = sys.stdin.read()
    elif code_file is not None:
        try:
            code = Path(code_file).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise click.UsageError("Could not read the code file.") from error
    assert code is not None
    if not code:
        raise click.UsageError("Code must not be empty.")

    try:
        token = load_token(token_file, os.environ)
        if session_id is None:
            session_id = resolve_session(url=url, token=token, file=file_path)
        result = execute_code(
            url=url,
            session_id=session_id,
            token=token,
            code=code,
            stdout=sys.stdout,
            stderr=sys.stderr,
            stream=stream,
        )
    except PairError as error:
        error_text, next_text = _failure_guidance(
            error, url=url, session_id=session_id
        )
        _emit_failure(
            error_text, next_text, session_id=session_id, stream=stream
        )
        ctx.exit(2)
    except KeyboardInterrupt:
        click.echo("Interrupted.", err=True)
        ctx.exit(1)

    next_text = None
    if not result.success:
        next_text = _kernel_next(
            result.stderr, url=display_url(url), session_id=session_id
        )

    if stream:
        if not result.success:
            if next_text:
                _emit_failure(
                    "Execution failed.",
                    next_text,
                    session_id=session_id,
                    stream=True,
                )
            ctx.exit(1)
        return

    payload: dict[str, object] = {
        "success": result.success,
        "output": result.output,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "session": {"id": session_id},
    }
    if next_text:
        payload["next"] = next_text
    click.echo(json.dumps(payload, indent=2))
    if not result.success:
        ctx.exit(1)


_TOKEN_NEXT = (
    "Pass --token-file <path> or set MARIMO_TOKEN. "
    'Check it with `test -n "$MARIMO_TOKEN"`. Never print the token. '
    "If you have no token, ask the user."
)
_HEADLESS_NEXT = (
    "A headless server has no session until a browser opens the notebook."
)


def _execute_prefix(url: str, session_id: str) -> str:
    """Shell-safe start of an execute command that targets one session."""
    return (
        "marimo pair execute "
        f"--url {shlex.quote(url)} --session {shlex.quote(session_id)}"
    )


def _inspect_command(url: str, session_id: str) -> str:
    return (
        f"{_execute_prefix(url, session_id)} --code-file - <<'PY'\n"
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as ctx:\n"
        "    for cell in ctx.cells.values():\n"
        "        print(cell.id, repr(cell.code), cell.status, cell.errors)\n"
        "PY"
    )


def _read_cell_command(url: str, session_id: str, cell_id: str) -> str:
    return (
        f"{_execute_prefix(url, session_id)} --code-file - <<'PY'\n"
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as ctx:\n"
        f"    cell = ctx.cells[{cell_id!r}]\n"
        "    print(cell.status, cell.errors, "
        "[o.data for o in cell.console_outputs])\n"
        "PY"
    )


def _help_cm_command(url: str, session_id: str) -> str:
    return (
        f"{_execute_prefix(url, session_id)} "
        "-c 'import marimo._code_mode as cm; help(cm)'"
    )


def _kernel_next(stderr: str, *, url: str, session_id: str) -> str | None:
    """Recovery guidance for the code-mode mistakes agents make most.

    Matches the traceback text the kernel returned. Unknown failures get
    no guidance rather than a guess.
    """
    if "asyncio.run() cannot be called from a running event loop" in stderr:
        return (
            "The kernel already runs an event loop. "
            "Write the block at top level:\n"
            "import marimo._code_mode as cm\n"
            "async with cm.get_context() as ctx:\n"
            "    ..."
        )
    match = re.search(r"KeyError: [\"']Cell '([^']+)' not found", stderr)
    if match:
        cell_id = match.group(1)
        return (
            f"Edits apply when the async with block exits, so '{cell_id}' "
            "does not exist yet in this block. "
            "Read it in a separate execute:\n"
            + _read_cell_command(url, session_id, cell_id)
        )
    match = re.search(
        r"AttributeError: '?([\w.]+)'? (?:object )?has no attribute '(\w+)'",
        stderr,
    )
    if match:
        owner, name = match.groups()
        hint = ""
        if owner.endswith("_CellsView"):
            hint = " Use ctx.cells[cid] or ctx.cells.values()."
        return (
            f"'{owner}' has no attribute '{name}'.{hint} For the full API:\n"
            + _help_cm_command(url, session_id)
        )
    return None


def _failure_guidance(
    error: PairError, *, url: str, session_id: str | None
) -> tuple[str, str | None]:
    """Error text and one `next` step for a failure before the kernel ran."""
    safe_url = display_url(url)
    if isinstance(error, AmbiguousSessionError):
        lines = [
            "Pass --session to choose one. Never switch sessions silently."
        ]
        lines.extend(
            f"{session_id}: marimo pair execute --url "
            f"{display_url(error.url)} --session {session_id} ..."
            for session_id in error.candidates
        )
        return str(error), "\n".join(lines)
    if isinstance(error, NoSessionError):
        return str(error), (
            f"{_HEADLESS_NEXT} Ask the user to open it, then:\n"
            f"marimo pair notebook list --url {display_url(error.url)}"
        )
    if isinstance(error, StaleSessionError):
        return "The session is stale.", (
            "Sessions change when the page reloads. List them again:\n"
            f"marimo pair notebook list --url {safe_url}"
        )
    message = str(error)
    if message == "Authentication failed.":
        return message, _TOKEN_NEXT
    if message.startswith("The server URL"):
        return message, ("Use the url field from:\nmarimo pair notebook list")
    if message == "Could not connect to the server.":
        return f"Could not connect to {safe_url}.", (
            "Check the URL. To find live servers: marimo pair notebook list"
        )
    if message == (
        "The execution response ended before completion was confirmed."
    ):
        return "Outcome unknown. The code may have run. Do not retry it.", (
            "Inspect the notebook first:\n"
            + _inspect_command(safe_url, session_id or "<SESSION>")
        )
    return message, None


def _emit_failure(
    error_text: str,
    next_text: str | None,
    *,
    session_id: str | None,
    stream: bool,
) -> None:
    if stream:
        click.echo(f"error: {error_text}", err=True)
        if next_text:
            first, *rest = next_text.splitlines()
            click.echo(f"  next: {first}", err=True)
            for line in rest:
                click.echo(f"  {line}", err=True)
        return
    payload: dict[str, object] = {
        "success": False,
        "error": error_text,
    }
    if next_text:
        payload["next"] = next_text
    payload.update(
        {
            "output": None,
            "stdout": None,
            "stderr": None,
            "session": {"id": session_id},
        }
    )
    click.echo(json.dumps(payload, indent=2))


@click.command(
    cls=_DocsCommand,
    help="Read notebook guidance on demand.",
    short_help="""Read notebook guidance on demand.""",
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
    "--file",
    "file_path",
    default=None,
    type=str,
    help="Notebook path or file key from the page URL.",
)
@click.option(
    "--session",
    "session_id",
    default=None,
    type=str,
    help="Current session ID to include in the prompt.",
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
    help="Prompt for an auth token and store it in a temp file. Leave empty if MARIMO_TOKEN is set.",
)
def prompt(
    url: str,
    file_path: str | None,
    session_id: str | None,
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
    preview = is_env_true("MARIMO_PAIR_NEXT")
    if not preview:
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

    token_file: Path | None = None
    if with_token:
        token = click.prompt(
            "Auth token (leave empty if MARIMO_TOKEN is set)",
            default="",
            show_default=False,
            hide_input=True,
            err=True,
        )
        if token:
            token_dir = _token_dir()
            url_hash = hashlib.sha256(url.encode()).hexdigest()[:6]
            token_file = token_dir / f"{url_hash}-token.txt"
            token_dir.mkdir(parents=True, exist_ok=True)
            # Open the token file for writing, creating it with restrictive
            # permissions if needed and truncating it if it already exists.
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            fd = os.open(token_file, flags, 0o600)
            try:
                os.write(fd, token.encode())
            finally:
                os.close(fd)

    if preview:
        click.echo(
            render_prompt(
                url=url,
                file_path=file_path,
                session_id=session_id,
                token_file=token_file,
            )
        )
        return

    # Preserve the file key exactly as supplied. Relative keys are resolved by
    # the server workspace and may refer to a remote or non-POSIX filesystem.
    # Shell-quote dynamic values because this command is copy-pasted into a
    # shell and paths may contain spaces or metacharacters.
    execute_cmd = f"execute-code.sh --url {shlex.quote(url)}"
    # The legacy script accepts only one selector. Match execute's precedence.
    if session_id:
        execute_cmd += f" --session {shlex.quote(session_id)}"
    elif file_path:
        execute_cmd += f" --file {shlex.quote(file_path)}"

    token_hint = ""
    if token_file is not None:
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


def _notebook_sort_key(notebook: dict[str, object]) -> tuple[str, str, str]:
    server = notebook["server"]
    assert isinstance(server, dict)
    return (
        str(server.get("url") or ""),
        str(notebook.get("name") or ""),
        str(notebook.get("path") or ""),
    )


def _group_notebooks(
    url: str, sessions: dict[str, dict[str, str | None]]
) -> list[dict[str, object]]:
    grouped: dict[str | None, dict[str, object]] = {}
    for session_id, session in sessions.items():
        key = session.get("path") or session.get("filename")
        notebook = grouped.setdefault(
            key,
            {
                "server": {"url": url},
                "name": session.get("filename"),
                "path": session.get("path"),
                "sessions": [],
            },
        )
        notebook_sessions = notebook["sessions"]
        assert isinstance(notebook_sessions, list)
        notebook_sessions.append({"id": session_id})

    for notebook in grouped.values():
        notebook_sessions = notebook["sessions"]
        assert isinstance(notebook_sessions, list)
        notebook_sessions.sort(key=lambda session: session["id"])
    return list(grouped.values())


@click.group(
    cls=ColoredGroup,
    help="Find active notebooks and their sessions.",
    short_help="""Find active notebooks and their sessions.""",
)
def notebook() -> None:
    pass


@click.command(
    name="list",
    cls=ColoredCommand,
    help="List active notebooks and their session IDs.",
    short_help="""List active notebooks and their session IDs.""",
)
@click.option(
    "--url",
    "urls",
    multiple=True,
    metavar="URL",
    help="Server URL. Repeat to list more than one server.",
)
@click.option(
    "--token-file",
    type=click.Path(path_type=Path, dir_okay=False),
    metavar="PATH",
    help="Read the server token from a local file. Otherwise use MARIMO_TOKEN, if set.",
)
def list_notebooks(urls: tuple[str, ...], token_file: Path | None) -> None:
    try:
        token = load_token(token_file, os.environ) if urls else None
    except PairInputError as error:
        raise click.UsageError(str(error)) from error
    selected_urls = list(urls) if urls else registry_urls()
    notebooks: list[dict[str, object]] = []
    warnings: list[str] = []

    for url in selected_urls:
        try:
            sessions = list_sessions(url=url, token=token)
        except PairError as error:
            if isinstance(error, PairInputError) and urls:
                raise click.UsageError(str(error)) from error
            message = str(error).rstrip(".")
            warnings.append(
                f"Server {display_url(url)} could not be read: {message}."
            )
        else:
            notebooks.extend(_group_notebooks(display_url(url), sessions))

    notebooks.sort(key=_notebook_sort_key)
    listing: dict[str, object] = {"notebooks": notebooks, "warnings": warnings}
    if any("Authentication failed" in warning for warning in warnings):
        listing["next"] = (
            "Pass --token-file <path> or set MARIMO_TOKEN, then run notebook "
            "list --url again. Never print the token."
        )
    elif not notebooks:
        listing["next"] = (
            f"No sessions found. {_HEADLESS_NEXT} If you know the server "
            "URL, pass --url. If the server needs a token, pass --token-file "
            "or set MARIMO_TOKEN."
        )
    click.echo(json.dumps(listing, indent=2))


notebook.add_command(list_notebooks)
pair.add_command(execute)
pair.add_command(docs)
pair.add_command(notebook)
pair.add_command(prompt)
