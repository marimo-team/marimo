# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import click
import msgspec

from marimo._cli.help_formatter import ColoredCommand, ColoredGroup
from marimo._cli.pair.client import (
    AmbiguousNotebookError,
    NoNotebookError,
    NoRuntimeError,
    NotebookUnsupportedError,
    PairConnectionError,
    PairError,
    PairInputError,
    RunConflictError,
    StaleNotebookError,
    display_url,
    execute as execute_code,
    list_sessions,
    load_token,
)
from marimo._cli.pair.connection import (
    ConnectionStore,
    connection_identity,
)
from marimo._cli.pair.discovery import list_running_notebooks
from marimo._cli.pair.forwarder import ForwarderConfig, start_forwarder
from marimo._cli.pair.harnesses import detect_target, environment_identity
from marimo._cli.pair.prompts import render_prompt
from marimo._cli.pair.target import ExecutionTarget, resolve_target
from marimo._server.ai.skills import utils as skills_utils
from marimo._server.host import HOST_API_PATH

_REFERENCES_DIR = (
    Path(skills_utils.__file__).parent / "marimo-pair" / "references"
)


_cached_token_dir: Path | None = None

F = TypeVar("F", bound=Callable[..., object])


def url_option(
    *,
    required: bool = False,
    multiple: bool = False,
    help_text: str = "Restrict notebook selection to this server.",
) -> Callable[[F], F]:
    return click.option(
        "--url",
        "urls" if multiple else "url",
        required=required,
        multiple=multiple,
        metavar="URL",
        help=help_text,
    )


def notebook_option(
    *,
    required: bool = False,
    help_text: str = "Alias for --session when selecting a notebook ID.",
) -> Callable[[F], F]:
    return click.option(
        "--notebook",
        "notebook_id",
        required=required,
        metavar="ID",
        help=help_text,
    )


def session_option(
    *,
    help_text: str = "Notebook ID or existing stable session ID.",
) -> Callable[[F], F]:
    return click.option(
        "--session", "session_id", metavar="ID", help=help_text
    )


token_option = click.option(
    "--token", help="Server token. Overrides MARIMO_TOKEN and local discovery."
)
token_file_option = click.option(
    "--token-file",
    type=click.Path(path_type=Path, dir_okay=False),
    metavar="PATH",
    help="Read the server token from a local file.",
)


def _token_dir() -> Path:
    import tempfile

    global _cached_token_dir
    if _cached_token_dir is None:
        _cached_token_dir = Path(tempfile.mkdtemp(prefix="marimo-pair-"))
    return _cached_token_dir


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
      Local discovery and execution use private credentials automatically.
      For explicit server access, pass --token or --token-file, or set
      MARIMO_TOKEN. Explicit credentials override local discovery.

    \b
    Workflow:
      Start a notebook if needed:
        marimo edit <notebook.py>
      Execute in the selected notebook:
        marimo pair execute --session <ID> --code 'print("hello")'
      For multiline Python, use --file <PATH>, or --file - for stdin:
        marimo pair execute --session <ID> --file - <<'PY'
        import marimo._code_mode as cm
        async with cm.get_context() as ctx:
            for cell in ctx.cells.values():
                print(cell.id, cell.code, cell.status)
        PY
      To receive notebook messages in Claude Code, Codex, or OpenCode 2.0:
        marimo pair connect --session <ID>

    \b
    Target selection:
      Use `marimo pair list` if you need to find the notebook ID.
      --session accepts a notebook ID or an existing stable session ID.
      Local notebook IDs resolve their URL automatically. Existing session IDs
      require --url. --notebook remains an alias for notebook IDs.
      With either selector, --url restricts discovery to that server.
      With --url alone, the server must have exactly one running notebook.
      If several notebooks are open, ask the user which one.
      Do not switch notebooks after authentication or connection errors,
      or when execution is unconfirmed.

    \b
    Agent messages (preview):
      Codex must use its shared daemon and support codex queue.
      Claude Code requires its native inbox on macOS or Linux.
      OpenCode 2.0 requires its registered local service.
      Inbound message settings still apply; messages can be held or refused.
      Notebook agent messages arrive here as messages from marimo.
      Oversized agent messages include a complete JSON file on this machine.
      Files remain after detach. Cleanup removes owned files older than 24 hours.
      Use pair detach --notebook <NOTEBOOK> to stop the inbox.

    \b
    Rules:
      Cells are the unit of work. The scratchpad is temporary; only code mode edits persist.
      Cells do not run on creation. Call run_cell after create_cell or edit_cell.
      Use async with. Do not await ctx methods.
      Install packages with ctx.packages.add, not uv add or pip. Installs change
      the project; confirm when the user did not ask.
      If an empty cell exists, edit_cell it instead of creating one.
      delete_cell drops the cell's variables. Ask before deleting.
      Do not edit the notebook file directly. Code mode is the only write path.

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
        marimo pair execute --session <ID> --code 'import marimo._code_mode as cm; help(cm)'
    """,
)
def pair() -> None:
    pass


def _validate_target_options(
    url: str | None,
    notebook_id: str | None,
    session_id: str | None,
    token: str | None,
    token_file: Path | None,
) -> None:
    if notebook_id is not None and session_id is not None:
        raise click.UsageError("Pass --session or --notebook, not both.")
    if session_id == "" or notebook_id == "":
        raise click.UsageError("The session ID must not be empty.")
    if token is not None and token_file is not None:
        raise click.UsageError("Pass --token or --token-file, not both.")
    if token == "":
        raise click.UsageError("The token must not be empty.")
    if url is None and session_id is None and notebook_id is None:
        raise click.UsageError(
            "Pass --session <ID> from `marimo pair list`, or --url <URL>."
        )


def _resolve_cli_target(
    *,
    url: str | None,
    notebook_id: str | None,
    session_id: str | None,
    token: str | None,
    token_file: Path | None,
    require_notebook: bool = False,
) -> ExecutionTarget:
    credential = (
        token if token is not None else load_token(token_file, os.environ)
    )
    return resolve_target(
        url=url,
        notebook_id=notebook_id,
        session_id=session_id,
        token=credential,
        require_notebook=require_notebook,
    )


@click.command(
    cls=ColoredCommand,
    help="""Run Python in the selected live notebook kernel's scratchpad.""",
    short_help="""Run Python in a live notebook.""",
)
@url_option()
@notebook_option()
@session_option()
@token_option
@token_file_option
@click.option(
    "--code",
    "-c",
    help="Inline Python.",
)
@click.option(
    "--file",
    "--code-file",
    "-f",
    "code_file",
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
    url: str | None,
    notebook_id: str | None,
    session_id: str | None,
    token_file: Path | None,
    token: str | None,
    code: str | None,
    code_file: str | None,
    stream: bool,
) -> None:
    _validate_target_options(url, notebook_id, session_id, token, token_file)
    if (code is None) == (code_file is None):
        raise click.UsageError("Specify exactly one of --code or --file.")

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

    selector = "--notebook" if notebook_id is not None else "--session"
    try:
        target = _resolve_cli_target(
            url=url,
            session_id=session_id,
            notebook_id=notebook_id,
            token=token,
            token_file=token_file,
        )
        url = target.url
        notebook_id = target.notebook_id
        session_id = target.id if notebook_id is None else None
        result = execute_code(
            url=target.url,
            session_id=target.id,
            token=target.token,
            code=code,
            stdout=sys.stdout,
            stderr=sys.stderr,
            stream=stream,
        )
    except PairError as error:
        error_text, next_text = _failure_guidance(
            error,
            url=url or "",
            notebook_id=notebook_id or session_id,
            selector=selector,
        )
        _emit_failure(
            error_text,
            next_text,
            notebook_id=notebook_id,
            session_id=session_id if notebook_id is None else None,
            stream=stream,
        )
        ctx.exit(2)
    except KeyboardInterrupt:
        click.echo("Interrupted.", err=True)
        ctx.exit(1)

    target_id = notebook_id or session_id
    assert target_id is not None
    next_text = None
    if not result.success:
        next_text = _kernel_next(
            result.stderr,
            url=display_url(url),
            notebook_id=target_id,
            selector=selector,
        )

    if stream:
        if not result.success:
            if next_text:
                _emit_failure(
                    "Execution failed.",
                    next_text,
                    notebook_id=notebook_id,
                    stream=True,
                )
            ctx.exit(1)
        return

    payload: dict[str, object] = {
        "success": result.success,
        "outcome": result.outcome,
        "output": result.output,
        "stdout": result.stdout,
        "stderr": result.stderr,
        ("session" if notebook_id is None else "notebook"): {
            "id": session_id if notebook_id is None else notebook_id
        },
    }
    if next_text:
        payload["next"] = next_text
    click.echo(json.dumps(payload, indent=2))
    if not result.success:
        ctx.exit(1)


_HEADLESS_NEXT = (
    "A headless server has no session until a browser opens the notebook."
)


def _execute_prefix(url: str, notebook_id: str, selector: str) -> str:
    """Shell-safe start of an execute command that targets one notebook."""
    return (
        "marimo pair execute "
        f"--url {shlex.quote(url)} {selector} {shlex.quote(notebook_id)}"
    )


def _inspect_command(url: str, notebook_id: str, selector: str) -> str:
    return (
        f"{_execute_prefix(url, notebook_id, selector)} --file - <<'PY'\n"
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as ctx:\n"
        "    for cell in ctx.cells.values():\n"
        "        print(cell.id, repr(cell.code), cell.status, cell.errors)\n"
        "PY"
    )


def _read_cell_command(
    url: str, notebook_id: str, cell_id: str, selector: str
) -> str:
    return (
        f"{_execute_prefix(url, notebook_id, selector)} --file - <<'PY'\n"
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as ctx:\n"
        f"    cell = ctx.cells[{cell_id!r}]\n"
        "    print(cell.status, cell.errors, "
        "[o.data for o in cell.console_outputs])\n"
        "PY"
    )


def _help_cm_command(url: str, notebook_id: str, selector: str) -> str:
    return (
        f"{_execute_prefix(url, notebook_id, selector)} "
        "--code 'import marimo._code_mode as cm; help(cm)'"
    )


def _kernel_next(
    stderr: str, *, url: str, notebook_id: str, selector: str
) -> str | None:
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
            + _read_cell_command(url, notebook_id, cell_id, selector)
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
            + _help_cm_command(url, notebook_id, selector)
        )
    return None


def _failure_guidance(
    error: PairError, *, url: str, notebook_id: str | None, selector: str
) -> tuple[str, str | None]:
    """Error text and one `next` step for a failure before the kernel ran."""
    safe_url = display_url(url)
    if isinstance(error, NoRuntimeError):
        return str(
            error
        ), "Open the saved notebook and start its kernel, then retry."
    if isinstance(error, RunConflictError):
        return (
            str(error),
            "Check the notebook's kernel state, then retry.",
        )
    if isinstance(error, AmbiguousNotebookError):
        if not error.url:
            return str(error), (
                "Run `marimo pair list` and pass --url to select the server."
            )
        lines = [
            f"Pass {selector} to choose one. Never switch notebooks silently."
        ]
        lines.extend(
            f"{notebook_id}: marimo pair execute --url "
            f"{display_url(error.url)} {selector} {shlex.quote(notebook_id)} ..."
            for notebook_id in error.candidates
        )
        return str(error), "\n".join(lines)
    if isinstance(error, NoNotebookError):
        if not error.url:
            return (
                str(error),
                "Run `marimo pair list` to find running local notebooks. Legacy session IDs require --url.",
            )
        return str(error), (
            f"{_HEADLESS_NEXT} Ask the user to open it, then:\n"
            f"marimo pair list --url {display_url(error.url)}"
        )
    if isinstance(error, NotebookUnsupportedError):
        return (
            (
                f"Server {safe_url} runs a marimo version without "
                "notebook_id. Upgrade marimo on the server."
            ),
            None,
        )
    if isinstance(error, StaleNotebookError):
        return (
            (
                f"No notebook {notebook_id or '<ID>'} on {safe_url}. "
                "Run pair list to find the current notebook."
            ),
            f"marimo pair list --url {safe_url}",
        )
    message = str(error)
    if message == "Authentication failed.":
        return (
            message,
            (
                "Run `marimo pair list` to refresh local discovery, or pass "
                "--token / --token-file for explicit server authentication."
            ),
        )
    if message.startswith("The server URL"):
        return message, ("Use the url field from:\nmarimo pair list")
    if isinstance(error, PairConnectionError):
        return f"Could not connect to {safe_url}.", (
            "Check the URL. To find live servers: marimo pair list"
        )
    if message == (
        "The execution response ended before completion was confirmed."
    ):
        return "Outcome unknown. The code may have run. Do not retry it.", (
            "Inspect the notebook first:\n"
            + _inspect_command(safe_url, notebook_id or "<ID>", selector)
        )
    return message, None


def _emit_failure(
    error_text: str,
    next_text: str | None,
    *,
    notebook_id: str | None,
    stream: bool,
    session_id: str | None = None,
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
            ("session" if session_id is not None else "notebook"): {
                "id": session_id if session_id is not None else notebook_id
            },
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
@url_option(required=True, help_text="URL to include in the prompt.")
@notebook_option(help_text="Notebook ID to include in the prompt.")
@session_option(
    help_text="Notebook ID or stable session ID to include in the prompt."
)
@click.option("--claude", is_flag=True, hidden=True, expose_value=False)
@click.option("--codex", is_flag=True, hidden=True, expose_value=False)
@click.option("--opencode", is_flag=True, hidden=True, expose_value=False)
@click.option(
    "--with-token",
    is_flag=True,
    default=False,
    help="Prompt for an auth token and store it in a temp file. Leave empty if MARIMO_TOKEN is set.",
)
def prompt(
    url: str,
    notebook_id: str | None,
    session_id: str | None,
    with_token: bool,
) -> None:
    """Generate CLI instructions for one Notebook or Session."""
    if notebook_id is not None and session_id is not None:
        raise click.UsageError("Pass --session or --notebook, not both.")
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

    click.echo(
        render_prompt(
            url=url,
            notebook_id=notebook_id,
            session_id=session_id,
            token_file=token_file,
        )
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
    for routing_id, session in sessions.items():
        key = session.get("path") or session.get("filename")
        notebook = grouped.setdefault(
            key,
            {
                "server": {"url": url},
                "name": session.get("filename"),
                "path": session.get("path"),
                "notebook_id": session.get("notebook_id"),
                "sessions": [],
            },
        )
        notebook_sessions = notebook["sessions"]
        assert isinstance(notebook_sessions, list)
        notebook_sessions.append(
            {"id": routing_id, "session_id": session["session_id"]}
        )

    for notebook in grouped.values():
        notebook_sessions = notebook["sessions"]
        assert isinstance(notebook_sessions, list)
        notebook_sessions.sort(key=lambda session: session["id"])
    return list(grouped.values())


@click.command(
    name="list",
    cls=ColoredCommand,
    help="List active notebooks and their host IDs.",
    short_help="""List active notebooks and their host IDs.""",
)
@url_option(
    multiple=True, help_text="Server URL. Repeat to list more than one server."
)
@token_file_option
def list_notebooks(urls: tuple[str, ...], token_file: Path | None) -> None:
    try:
        token = load_token(token_file, os.environ) if urls else None
    except PairInputError as error:
        raise click.UsageError(str(error)) from error
    if not urls:
        local_listing = list_running_notebooks()
        payload = msgspec.to_builtins(local_listing)
        if not local_listing.notebooks:
            payload["next"] = (
                "No running notebooks found. Open a notebook with "
                "`marimo edit <notebook.py>`, then run `marimo pair list` again."
                if not local_listing.warnings
                else "Some local servers could not be listed. Check the warnings, "
                "then run `marimo pair list` again."
            )
        click.echo(json.dumps(payload, indent=2))
        return
    selected_urls = list(urls)
    notebooks: list[dict[str, object]] = []
    warnings: list[str] = []

    for url in selected_urls:
        try:
            sessions = list_sessions(url=url, token=token)
        except PairError as error:
            if isinstance(error, PairInputError) and urls:
                raise click.UsageError(str(error)) from error
            if isinstance(error, NotebookUnsupportedError):
                warnings.append(
                    f"Server {display_url(url)} runs a marimo version "
                    "without notebook_id. Upgrade marimo on the server."
                )
            else:
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
            "Pass --token-file <path>, then run pair list --url again. "
            "If no file exists, check for MARIMO_TOKEN with "
            '`test -n "$MARIMO_TOKEN"`. Never print the token.'
        )
    elif not notebooks:
        listing["next"] = (
            "No sessions found. If a server is running, pass --url, and "
            "--token-file <path> if it needs a token. Otherwise start one in "
            "the background: `marimo edit <notebook.py>`, then run "
            "`marimo pair list` again."
        )
    click.echo(json.dumps(listing, indent=2))


@click.command(
    cls=ColoredCommand,
    help=(
        "Connect this harness inbox to a live notebook.\n\n"
        "Supported harnesses: Codex, Claude Code, and OpenCode (macOS/Linux).\n\n"
        "OpenCode 2.0 requires its registered local service.\n\n"
        "For other harnesses, use pair execute to work with the notebook."
    ),
)
@url_option()
@notebook_option()
@session_option()
@token_option
@token_file_option
@click.option(
    "--harness",
    type=click.Choice(["codex", "claude", "opencode"]),
    help="Select the inbox harness.",
)
@click.option(
    "--pid",
    type=click.IntRange(min=1),
    help=(
        "Process to track for connection lifetime. Defaults to the current harness. "
        "Its start time is captured automatically."
    ),
)
def connect(
    url: str | None,
    notebook_id: str | None,
    session_id: str | None,
    token: str | None,
    token_file: Path | None,
    harness: str | None,
    pid: int | None,
) -> None:
    _validate_target_options(url, notebook_id, session_id, token, token_file)
    try:
        selected = _resolve_cli_target(
            url=url,
            session_id=session_id,
            notebook_id=notebook_id,
            token=token,
            token_file=token_file,
            require_notebook=True,
        )
        assert selected.notebook_id is not None
        notebook_id = selected.notebook_id
        _selected_harness, target = detect_target(os.environ, harness, pid)
        identity = connection_identity(
            notebook_id, target.kind, target.address
        )
        store = ConnectionStore()
        with store.locked(identity):
            store.stop(identity)
            start_forwarder(
                ForwarderConfig(
                    selected.url.rstrip("/").removesuffix(HOST_API_PATH)
                    + HOST_API_PATH,
                    notebook_id,
                    identity,
                    selected.token,
                    target,
                ),
                store,
            )
        click.echo(
            f"Connected as {target.label}. Agent messages from this notebook arrive here as messages from marimo."
        )
    except (PairError, OSError) as error:
        raise click.ClickException(str(error)) from error


@click.command(
    cls=ColoredCommand,
    help="Stop the forwarder and detach its notebook inbox.",
)
@notebook_option(required=True, help_text="Notebook ID to disconnect.")
@click.option(
    "--harness",
    type=click.Choice(["codex", "claude", "opencode"]),
    help="Select the harness to disconnect.",
)
def detach(notebook_id: str, harness: str | None) -> None:
    try:
        store = ConnectionStore()
        kind, conversation = environment_identity(os.environ, kind=harness)
        selected = store.select(
            notebook_id, kind=kind, conversation=conversation
        )
        if selected is not None:
            with store.locked(selected.identity):
                store.stop(selected.identity)
        click.echo(
            "Detached." if selected is not None else "No matching connection."
        )
    except (PairError, OSError) as error:
        raise click.ClickException(str(error)) from error


pair.add_command(connect)
pair.add_command(detach)
pair.add_command(execute)
pair.add_command(docs)
pair.add_command(list_notebooks)
pair.add_command(prompt)
