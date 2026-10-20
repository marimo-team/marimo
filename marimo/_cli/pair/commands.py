# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path

import click

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
    execute_editor,
    list_sessions,
    load_token,
    registry_urls,
    resolve_execution_target,
    resolve_host,
)
from marimo._cli.pair.connection import (
    ConnectionStore,
    connection_identity,
)
from marimo._cli.pair.forwarder import ForwarderConfig, start_forwarder
from marimo._cli.pair.harnesses import detect_target, environment_identity
from marimo._cli.pair.prompts import render_prompt
from marimo._server.ai.skills import utils as skills_utils

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
      Notebook discovery uses the editor token. Pass --token-file <PATH> to
      notebook list or execute without --notebook when a token is required.
      Host commands read their token from the private local host record.

    \b
    Workflow:
      If no server is running, start one in the background:
        marimo edit <notebook.py> --no-token
      If you do not have the server URL or notebook ID:
        marimo pair notebook list
      Connect to the notebook before waiting for work.
      Run marimo pair connect --help to check supported harnesses.
      If your harness is supported, run:
        marimo pair connect --url <URL> --notebook <NOTEBOOK>
      Otherwise, work with the notebook using pair execute:
      marimo pair execute --url <URL> --session <SESSION> --code-file - <<'PY'
      import marimo._code_mode as cm
      async with cm.get_context() as ctx:
          ctx.packages.add("pandas")
          cid = ctx.create_cell("import pandas as pd")
          ctx.run_cell(cid)
      PY
      marimo pair execute --url <URL> --notebook <NOTEBOOK> --code-file - <<'PY'
      import marimo._code_mode as cm
      async with cm.get_context() as ctx:
          cell = ctx.cells["<CELL_ID>"]
          print(cell.status, cell.errors, [o.data for o in cell.console_outputs])
      PY

    \b
    Target selection:
      --session takes a stable session_id for editor execution.
      --notebook takes notebook_id for host execution. It survives
      kernel restarts and page reloads. Only saved notebooks inside the project
      root have a host notebook ID. Host commands need a local edit server.
      If several notebooks are open, ask the user which one.
      Do not switch notebooks after authentication or connection errors,
      or when execution is unconfirmed.

    \b
    Agent messages (preview):
      Inside Codex, Claude Code, or OpenCode, run:
        marimo pair connect --url <URL> --notebook <NOTEBOOK>.
      Codex must use its shared daemon and support codex queue.
      Claude Code requires its native inbox on macOS or Linux.
      OpenCode 2.x requires its registered local service.
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
        marimo pair execute --url <URL> --notebook <NOTEBOOK> -c 'import marimo._code_mode as cm; help(cm)'
    """,
)
def pair() -> None:
    pass


@click.command(
    cls=ColoredCommand,
    help="""Run Python in the selected live notebook kernel's scratchpad.""",
    short_help="""Run Python in a live notebook.""",
)
@click.option(
    "--url",
    required=True,
    metavar="URL",
    help="Server URL.",
)
@click.option(
    "--notebook",
    "notebook_id",
    required=False,
    metavar="ID",
    help="Host notebook_id from marimo pair notebook list.",
)
@click.option(
    "--session",
    "session_id",
    default=None,
    help="Stable Session ID from notebook list. Host execution is preferred when available.",
)
@click.option(
    "--token-file",
    type=click.Path(path_type=Path, dir_okay=False),
    metavar="PATH",
    help="Read the server token from a local file.",
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
    notebook_id: str | None,
    session_id: str | None,
    token_file: Path | None,
    code: str | None,
    code_file: str | None,
    stream: bool,
) -> None:
    if notebook_id is not None and session_id is not None:
        raise click.UsageError("Pass --session or --notebook, not both.")
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

    editor = notebook_id is None
    selector = "--session" if editor else "--notebook"
    try:
        token = (
            load_token(token_file, os.environ) if notebook_id is None else None
        )
        if notebook_id is None:
            notebook_id, session_id = resolve_execution_target(
                url=url, token=token, session_id=session_id
            )
        editor = notebook_id is None
        selector = "--session" if editor else "--notebook"
        if editor:
            assert session_id is not None
            result = execute_editor(
                url=url,
                session_id=session_id,
                token=token,
                code=code,
                stdout=sys.stdout,
                stderr=sys.stderr,
                stream=stream,
            )
        else:
            assert notebook_id is not None
            host = resolve_host(url)
            result = execute_code(
                url=host.url,
                notebook_id=notebook_id,
                token=host.token,
                code=code,
                stdout=sys.stdout,
                stderr=sys.stderr,
                stream=stream,
            )
    except PairError as error:
        error_text, next_text = _failure_guidance(
            error,
            url=url,
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
        ("session" if editor else "notebook"): {
            "id": session_id if editor else notebook_id
        },
    }
    if session_id is not None:
        payload["session"] = {"id": session_id}
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
        f"{_execute_prefix(url, notebook_id, selector)} --code-file - <<'PY'\n"
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
        f"{_execute_prefix(url, notebook_id, selector)} --code-file - <<'PY'\n"
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
        "-c 'import marimo._code_mode as cm; help(cm)'"
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
            "Wait for the active run to finish. Inspect its results before retrying.",
        )
    if isinstance(error, AmbiguousNotebookError):
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
        return str(error), (
            f"{_HEADLESS_NEXT} Ask the user to open it, then:\n"
            f"marimo pair notebook list --url {display_url(error.url)}"
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
                "Run notebook list to find the current host notebook."
            ),
            f"marimo pair notebook list --url {safe_url}",
        )
    message = str(error)
    if message == "Authentication failed.":
        return (
            message,
            "Restart the local edit server and retry host discovery."
            if selector == "--notebook"
            else "Pass --token-file <path> or set MARIMO_TOKEN for editor authentication.",
        )
    if message.startswith("The server URL"):
        return message, ("Use the url field from:\nmarimo pair notebook list")
    if isinstance(error, PairConnectionError):
        return f"Could not connect to {safe_url}.", (
            "Check the URL. To find live servers: marimo pair notebook list"
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
@click.option(
    "--url",
    required=True,
    type=str,
    help="URL of the running marimo kernel.",
)
@click.option(
    "--notebook",
    "notebook_id",
    default=None,
    type=str,
    help="Host notebook_id to include in the prompt.",
)
@click.option(
    "--session",
    "session_id",
    default=None,
    help="Stable Session ID from notebook list. Host execution is preferred when available.",
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


@click.group(
    cls=ColoredGroup,
    help="Find active notebooks and their IDs.",
    short_help="""Find active notebooks and their IDs.""",
)
def notebook() -> None:
    pass


@click.command(
    name="list",
    cls=ColoredCommand,
    help="List active notebooks and their host IDs.",
    short_help="""List active notebooks and their host IDs.""",
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
    help="Read the server token from a local file.",
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
            "Pass --token-file <path>, then run notebook list --url again. "
            "If no file exists, check for MARIMO_TOKEN with "
            '`test -n "$MARIMO_TOKEN"`. Never print the token.'
        )
    elif not notebooks:
        listing["next"] = (
            "No sessions found. If a server is running, pass --url, and "
            "--token-file <path> if it needs a token. Otherwise start one in "
            "the background: `marimo edit <notebook.py> --no-token`, then run "
            "`marimo pair notebook list` again."
        )
    click.echo(json.dumps(listing, indent=2))


notebook.add_command(list_notebooks)


@click.command(
    cls=ColoredCommand,
    help=(
        "Connect this harness inbox to a live notebook.\n\n"
        "Supported harnesses: Codex, Claude Code, and OpenCode (macOS/Linux).\n\n"
        "OpenCode 2.x requires its registered local service.\n\n"
        "For other harnesses, use pair execute to work with the notebook."
    ),
)
@click.option("--url", required=True, help="Server URL.")
@click.option(
    "--notebook",
    "notebook_id",
    required=True,
    help="Host notebook ID from notebook list.",
)
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
    url: str, notebook_id: str, harness: str | None, pid: int | None
) -> None:
    try:
        _selected_harness, target = detect_target(os.environ, harness, pid)
        host = resolve_host(url)
        identity = connection_identity(
            notebook_id, target.kind, target.address
        )
        store = ConnectionStore()
        with store.locked(identity):
            store.stop(identity)
            start_forwarder(
                ForwarderConfig(
                    host.url, notebook_id, identity, host.token, target
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
@click.option(
    "--notebook",
    "notebook_id",
    required=True,
    help="Host notebook ID from notebook list.",
)
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
pair.add_command(notebook)
pair.add_command(prompt)
