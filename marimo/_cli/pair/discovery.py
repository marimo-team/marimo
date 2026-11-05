# Copyright 2026 Marimo. All rights reserved.
"""Find running notebooks through private local discovery records."""

from __future__ import annotations

import http.client
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from marimo._cli.pair.client import (
    HostEndpoint,
    PairError,
    display_url,
    iter_sse,
    open_response,
)
from marimo._core import protocol
from marimo._server.host import HOST_API_PATH
from marimo._server.host.record import discover_hosts

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

_TIMEOUT = 5.0


class RunningNotebook(msgspec.Struct, frozen=True):
    id: str
    name: str
    path: str | None
    url: str
    status: protocol.RuntimeStatus


class Listing(msgspec.Struct):
    notebooks: list[RunningNotebook]
    warnings: list[str]


def list_running_notebooks(
    hosts: Iterable[HostEndpoint] | None = None,
) -> Listing:
    """Read complete snapshots, retaining results from available servers."""
    selected = (
        list(hosts)
        if hosts is not None
        else [
            HostEndpoint(record.url, record.token)
            for record in discover_hosts()
        ]
    )
    listing = Listing([], [])
    if selected:
        with ThreadPoolExecutor(max_workers=min(8, len(selected))) as pool:
            for result in pool.map(_read_host, selected):
                listing.notebooks.extend(result.notebooks)
                listing.warnings.extend(result.warnings)
    listing.notebooks.sort(key=lambda n: (n.name, n.path or "", n.url, n.id))
    return listing


def _bounded_lines(lines: Iterable[bytes]) -> Iterator[bytes]:
    deadline = time.monotonic() + _TIMEOUT
    for line in lines:
        if time.monotonic() >= deadline:
            raise TimeoutError("The notebook catalog did not finish in time.")
        yield line


def _read_host(host: HostEndpoint) -> Listing:
    try:
        return _snapshot(host)
    except (
        PairError,
        OSError,
        http.client.HTTPException,
        ValueError,
        msgspec.DecodeError,
    ):
        # Response bodies can contain credentials; diagnostics name only the server.
        return Listing(
            [], [f"Could not list notebooks on {display_url(host.url)}."]
        )


def _snapshot(host: HostEndpoint) -> Listing:
    response = open_response(
        method="GET",
        url=host.url.rstrip("/") + "/events?types=project,notebook,runtime",
        headers={"Authorization": f"Bearer {host.token}"},
        body=None,
        read_timeout=_TIMEOUT,
    )
    projects: dict[protocol.ProjectId, protocol.Project] = {}
    notebooks: dict[protocol.NotebookId, protocol.Notebook] = {}
    runtimes: dict[protocol.NotebookId, protocol.Runtime] = {}
    try:
        for event in iter_sse(_bounded_lines(response)):
            if event.name == "project":
                project = msgspec.json.decode(
                    event.data, type=protocol.ProjectMessage
                ).project
                projects[project.id] = project
            elif event.name == "notebook":
                notebook = msgspec.json.decode(
                    event.data, type=protocol.NotebookMessage
                ).notebook
                notebooks[notebook.id] = notebook
            elif event.name == "runtime":
                runtime = msgspec.json.decode(
                    event.data, type=protocol.RuntimeMessage
                ).runtime
                runtimes[runtime.notebook_id] = runtime
            elif event.name == "reset":
                projects.clear()
                notebooks.clear()
                runtimes.clear()
            elif event.name == "ready":
                break
        else:
            raise PairError("The notebook catalog ended before it was ready.")
    finally:
        response.close()

    url = host.url.rstrip("/").removesuffix(HOST_API_PATH)
    listing = Listing([], [])
    for project in projects.values():
        if project.status != "indexed":
            listing.warnings.append(
                f"Project {project.name!r} on {url} is {project.status}; some notebooks may be missing."
            )
    for notebook in notebooks.values():
        current_runtime = runtimes.get(notebook.id)
        if current_runtime is None or current_runtime.status != "running":
            continue
        current_project = projects.get(notebook.project_id)
        path = notebook.path
        if (
            path is not None
            and current_project is not None
            and current_project.root is not None
        ):
            path = str(Path(current_project.root) / path)
        listing.notebooks.append(
            RunningNotebook(
                notebook.id, notebook.name, path, url, current_runtime.status
            )
        )
    return listing
