# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
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
    Workflow:
      If you do not have the server URL and session id:
        marimo pair notebook list
      marimo pair execute --url <URL> --session <SESSION> --code-file - <<'PY'
      import marimo._code_mode as cm
      async with cm.get_context() as ctx:
          ctx.packages.add("pandas")
          cid = ctx.create_cell("import pandas as pd")
          ctx.run_cell(cid)
      PY
      marimo pair execute --url <URL> --session <SESSION> --code-file - <<'PY'
      import marimo._code_mode as cm
      async with cm.get_context() as ctx:
          cell = ctx.cells["<CELL_ID>"]
          print(cell.status, cell.errors, [o.data for o in cell.console_outputs])
      PY

    \b
    Rules:
      Cells are the unit of work. The scratchpad is temporary; only cm edits persist.
      Cells do not run on creation. Call run_cell after create_cell or edit_cell.
      Use async with. Do not await ctx methods.
      Install packages with ctx.packages.add, not uv add or pip. Installs change
      the project; confirm when the user did not ask.
      If an empty cell exists, edit_cell it instead of creating one.
      delete_cell drops the cell's variables. Ask before deleting.
      Session IDs change when the page reloads. If execute reports a stale
      session, run notebook list again.

    \b
    Code-mode API (this marimo version):
      ctx.cells                 # each has .id .code .status .errors .console_outputs
      ctx.create_cell(code)     # returns the new cell id
      ctx.edit_cell(cid, code)
      ctx.run_cell(cid)
      ctx.delete_cell(cid)
      ctx.packages.add("pandas>=2")  # queued, installs on exit
      If a cm call fails, run help(cm):
        marimo pair execute --url <URL> --session <SESSION> -c 'import marimo._code_mode as cm; help(cm)'
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


def _inspect_command(url: str, session_id: str) -> str:
    return (
        f"marimo pair execute --url {url} --session {session_id} "
        "--code-file - <<'PY'\n"
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as ctx:\n"
        "    for cell in ctx.cells.values():\n"
        "        print(cell.id, repr(cell.code), cell.status, cell.errors)\n"
        "PY"
    )


def _read_cell_command(url: str, session_id: str, cell_id: str) -> str:
    return (
        f"marimo pair execute --url {url} --session {session_id} "
        "--code-file - <<'PY'\n"
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as ctx:\n"
        f'    cell = ctx.cells["{cell_id}"]\n'
        "    print(cell.status, cell.errors, "
        "[o.data for o in cell.console_outputs])\n"
        "PY"
    )


def _help_cm_command(url: str, session_id: str) -> str:
    return (
        f"marimo pair execute --url {url} --session {session_id} "
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
    short_help="""Generate pairing instructions.""",
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
@click.option("--claude", is_flag=True, hidden=True, expose_value=False)
@click.option("--codex", is_flag=True, hidden=True, expose_value=False)
@click.option("--opencode", is_flag=True, hidden=True, expose_value=False)
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
    with_token: bool,
) -> None:
    """
    Generate a prompt for pair programming.

    Example usage:

        claude "$(marimo pair prompt --url 'https://localhost:8000' --session 'session-123')"
        codex "$(marimo pair prompt --url 'https://localhost:8000' --session 'session-123')"
        opencode --prompt "$(marimo pair prompt --url 'https://localhost:8000' --session 'session-123')"

        # Connect to a specific notebook
        claude "$(marimo pair prompt --url 'https://localhost:8000' --session 'session-123' --file 'notebooks/example.py')"

        # With an auth token
        claude "$(marimo pair prompt --url 'https://localhost:8000' --session 'session-123' --with-token)"
    """
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
        "Start with: marimo pair --help\n"
        "If marimo is not on your PATH, run it the same way this notebook "
        "server was started.\n\n"
        "Once connected, run `import marimo as mo; "
        'mo.status.toast("Ready to pair")` to let the user know you are ready.'
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
