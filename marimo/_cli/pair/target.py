# Copyright 2026 Marimo. All rights reserved.
"""Resolve the notebook selected by a Pair command."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit

from marimo._cli.pair.client import (
    AmbiguousNotebookError,
    NoNotebookError,
    NotebookUnsupportedError,
    PairError,
    display_url,
    find_host,
    list_sessions,
    resolve_host,
)
from marimo._cli.pair.discovery import list_running_notebooks
from marimo._server.host import HOST_API_PATH
from marimo._server.host.auth import is_loopback


@dataclass(frozen=True)
class ExecutionTarget:
    url: str
    id: str
    token: str | None = field(repr=False)
    notebook_id: str | None = None


def resolve_inbox_target(selected: ExecutionTarget) -> ExecutionTarget:
    """Use the matching local host credential after session selection."""
    if find_host(selected.url) is None:
        return selected
    return resolve_target(
        url=selected.url,
        session_id=selected.notebook_id,
        token=None,
        require_notebook=True,
    )


def resolve_target(
    *,
    url: str | None,
    session_id: str | None,
    token: str | None,
    notebook_id: str | None = None,
    require_notebook: bool = False,
) -> ExecutionTarget:
    selected_id = notebook_id if notebook_id is not None else session_id
    host = find_host(url) if url is not None and token is None else None
    if host is not None:
        url = host.url.rstrip("/").removesuffix(HOST_API_PATH)

    if url is None or host is not None:
        listing = list_running_notebooks([host] if host is not None else None)
        if listing.warnings and selected_id is None:
            raise PairError(" ".join(listing.warnings))
        found = [
            notebook
            for notebook in listing.notebooks
            if selected_id is None or notebook.id == selected_id
        ]
        if not found and listing.warnings:
            raise PairError(" ".join(listing.warnings))
        # The catalog has no legacy session IDs. Only an explicit --session
        # and URL can defer that lookup to the selected server.
        if not found and host is not None and session_id is not None:
            assert url is not None
            if not require_notebook:
                return ExecutionTarget(url, session_id, host.token)
            return _session_target(
                url, session_id, None, host.token, require_notebook=True
            )
        _require_one([n.id for n in found], url, selected_id)
        notebook = found[0]
        selected_host = (
            host if host is not None else resolve_host(notebook.url)
        )
        return ExecutionTarget(
            notebook.url,
            notebook.id,
            token if token is not None else selected_host.token,
            notebook.id,
        )

    selected = _session_target(
        url, session_id, notebook_id, token, require_notebook=require_notebook
    )
    if (
        require_notebook
        and token is None
        and is_loopback(urlsplit(url).hostname or "")
    ):
        # A local frontend proxy can expose sessions at a different port.
        # Match its verified notebook ID before using a discovered credential.
        return resolve_target(
            url=None,
            session_id=selected.notebook_id,
            token=None,
            require_notebook=True,
        )
    return selected


def _session_target(
    url: str,
    session_id: str | None,
    notebook_id: str | None,
    token: str | None,
    *,
    require_notebook: bool = False,
) -> ExecutionTarget:
    selected_id = notebook_id if notebook_id is not None else session_id
    sessions = list_sessions(url=url, token=token)
    candidates = {
        str(s["session_id"]): s
        for s in sessions.values()
        if selected_id is None
        or selected_id == s.get("notebook_id")
        or session_id == s["session_id"]
    }
    _require_one(list(candidates), url, selected_id)
    selected = next(iter(candidates.values()))
    if require_notebook and selected.get("notebook_id") is None:
        raise NotebookUnsupportedError(
            "This server does not expose a host notebook ID. Upgrade marimo on the server."
        )
    return ExecutionTarget(
        url, str(selected["session_id"]), token, selected.get("notebook_id")
    )


def _require_one(
    ids: list[str], url: str | None, selected: str | None
) -> None:
    scope = f"on {display_url(url)}" if url is not None else "on this machine"
    if not ids:
        detail = f" matches {selected!r}" if selected is not None else ""
        raise NoNotebookError(
            f"No running notebook{detail} {scope}.",
            url=display_url(url) if url else "",
        )
    if len(ids) > 1:
        raise AmbiguousNotebookError(
            f"Found {len(ids)} running notebooks {scope}; pass --url and an ID.",
            url=display_url(url) if url else "",
            candidates=tuple(sorted(ids)),
        )
