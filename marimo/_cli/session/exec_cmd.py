# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys

import click


@click.command(
    name="exec",
    help="Execute Python code in a running marimo session's scratchpad.",
)
@click.option(
    "-c",
    "--code",
    required=True,
    type=str,
    help="Python code to execute.",
)
@click.option(
    "-p",
    "--port",
    default=None,
    type=int,
    help="Target a session by port.",
)
@click.option(
    "--id",
    "session_id",
    default=None,
    type=str,
    help="Target a specific session ID on the server.",
)
def exec_cmd(
    code: str,
    port: int | None,
    session_id: str | None,
) -> None:
    from marimo._server.session_registry import SessionRegistryReader

    entry = _resolve_entry(SessionRegistryReader.read_all(), port)

    # If no session_id specified, we need to discover one from the server
    if session_id is None:
        session_id = _discover_session_id(entry)
        if session_id is None:
            click.echo(
                "No active session found on the server. "
                "Make sure a notebook is open in the browser.",
                err=True,
            )
            sys.exit(1)

    # Execute code via the sync endpoint
    from marimo._utils.requests import RequestError, post

    url = _base_url(entry) + "/api/kernel/scratchpad/execute"
    params = _auth_params(entry)

    try:
        resp = post(
            url,
            json_data={"code": code},
            headers={"Marimo-Session-Id": session_id},
            params=params,
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
    except RequestError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    # Print output
    if result.get("stdout"):
        for line in result["stdout"]:
            click.echo(line, nl=False)

    if result.get("output"):
        click.echo(result["output"])

    if result.get("stderr"):
        for line in result["stderr"]:
            click.echo(line, err=True, nl=False)

    if result.get("errors"):
        for err in result["errors"]:
            click.echo(err, err=True)

    if result.get("error"):
        click.echo(result["error"], err=True)

    if not result.get("success", True):
        sys.exit(1)


def _base_url(entry: object) -> str:
    from marimo._server.session_registry import SessionRegistryEntry

    assert isinstance(entry, SessionRegistryEntry)
    return f"http://{entry.host}:{entry.port}{entry.base_url}"


def _auth_params(entry: object) -> dict[str, str] | None:
    from marimo._server.session_registry import SessionRegistryEntry

    assert isinstance(entry, SessionRegistryEntry)
    if entry.auth_token:
        return {"access_token": entry.auth_token}
    return None


def _resolve_entry(entries: list[object], port: int | None) -> object:
    """Resolve a single registry entry from the list, or exit with error."""
    from marimo._server.session_registry import SessionRegistryEntry

    if not entries:
        click.echo("No running marimo sessions found.", err=True)
        sys.exit(1)

    if port is not None:
        for e in entries:
            assert isinstance(e, SessionRegistryEntry)
            if e.port == port:
                return e
        click.echo(
            f"No running marimo session found on port {port}.",
            err=True,
        )
        sys.exit(1)

    if len(entries) == 1:
        return entries[0]

    click.echo(
        "Multiple running sessions found. Use --port to specify which one:",
        err=True,
    )
    for e in entries:
        assert isinstance(e, SessionRegistryEntry)
        click.echo(
            f"  {e.server_id}  {e.notebook_path or '(multi/new)'}",
            err=True,
        )
    sys.exit(1)


def _discover_session_id(entry: object) -> str | None:
    """Query the server's /api/sessions endpoint to find a session ID."""
    from marimo._utils.requests import RequestError, get

    url = _base_url(entry) + "/api/sessions"
    params = _auth_params(entry)

    try:
        resp = get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data:
            session_ids = list(data.keys())
            if len(session_ids) > 1:
                click.echo(
                    "Multiple sessions found on the server. "
                    "Use --id to specify which one:",
                    err=True,
                )
                for sid in session_ids:
                    info = data[sid]
                    click.echo(
                        f"  {sid}  {info.get('filename', '')}",
                        err=True,
                    )
                sys.exit(1)
            return str(session_ids[0])
    except RequestError:
        pass

    return None
