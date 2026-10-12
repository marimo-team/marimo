# Copyright 2026 Marimo. All rights reserved.
"""Configure a disposable host through its discovery record."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlsplit
from uuid import uuid4

import httpx
import pytest
from contract import Host, accepted, objects, validate

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--record", help="Path to a running host's discovery record"
    )
    parser.addoption("--host-timeout", type=float, default=10.0)
    parser.addoption(
        "--slow", action="store_true", help="Include idle ping checks"
    )
    parser.addoption("--require-operation", action="append", default=[])


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--require-operation") and not config.getoption(
        "--record"
    ):
        raise pytest.UsageError("--require-operation needs --record")


@pytest.fixture(scope="session")
def record(pytestconfig: pytest.Config) -> dict[str, Any]:
    import psutil

    filename = pytestconfig.getoption("--record")
    if filename is None:
        pytest.skip("pass --record to check a running host")
    path = Path(filename)
    if os.name == "posix":
        for resource in (path, path.parent):
            stat = resource.stat()
            assert stat.st_uid == os.getuid(), (
                "record and directory must belong to this user"
            )
            assert stat.st_mode & 0o077 == 0, (
                "record and directory must be private"
            )
    value = json.loads(path.read_text(encoding="utf-8"))
    validate("HostRecord", value)
    url = urlsplit(value["url"])
    assert url.scheme == "http"
    assert url.hostname in ("127.0.0.1", "::1")
    assert url.username is None
    assert url.password is None
    assert not url.query
    assert not url.fragment
    process = psutil.Process(value["process"]["pid"])
    started = datetime.fromisoformat(
        value["process"]["started_at"].replace("Z", "+00:00")
    )
    assert abs(process.create_time() - started.timestamp()) < 1, (
        "stale process identity"
    )
    return value


@pytest.fixture
async def host(
    record: dict[str, Any], pytestconfig: pytest.Config
) -> AsyncIterator[Host]:
    timeout = pytestconfig.getoption("--host-timeout")
    assert timeout > 0
    async with httpx.AsyncClient(
        base_url=record["url"].rstrip("/") + "/",
        headers={"Authorization": f"Bearer {record['token']}"},
        timeout=timeout,
        trust_env=False,
        follow_redirects=False,
    ) as client:
        yield Host(client, timeout)


@pytest.fixture
async def catalog(host: Host) -> list:
    return await host.snapshot()


@pytest.fixture
async def scratch(host: Host, catalog: list) -> AsyncIterator[dict[str, Any]]:
    projects = objects(catalog, "project")
    available = set(objects(catalog, "host")[0]["operations"])
    if not {"notebook.create", "notebook.delete"} <= available:
        pytest.skip(
            "scratch checks require notebook.create and notebook.delete"
        )
    project = next(
        (p for p in projects if "notebook.create" in p["operations"]), None
    )
    if project is None:
        pytest.skip("no project permits notebook.create")
    name = f"conformance-{uuid4().hex}.py"
    body = {
        "project_id": project["id"],
        "path" if project["root"] else "name": name,
    }
    notebook = accepted(
        await host.request("POST", "/notebooks", json=body), 201, "Notebook"
    )
    existing = {n["id"] for n in objects(catalog, "notebook")}
    assert notebook["id"] not in existing, (
        "create claimed an existing notebook"
    )
    assert notebook["project_id"] == project["id"]
    assert (
        notebook["path"] == name
        if project["root"]
        else notebook["name"] == name
    )
    try:
        yield notebook
    finally:
        path = f"/notebooks/{quote(notebook['id'], safe='')}"
        if "runtime.stop" in notebook["operations"]:
            response = await host.request("DELETE", path + "/runtime")
            assert response.status_code in (202, 409), (
                "could not clean up runtime"
            )
            if response.status_code == 202:
                async with host.watch(path + "/events") as watch:
                    snapshot = await watch.ready()
                    if objects(snapshot, "runtime"):
                        await watch.until(
                            lambda f: f.event == "runtime.removed"
                        )
        response = await host.request("DELETE", path)
        assert response.status_code in (204, 404), (
            "could not clean up scratch notebook"
        )
