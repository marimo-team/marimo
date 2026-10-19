# Copyright 2026 Marimo. All rights reserved.
"""Check a running host through the public HTTP and SSE interface."""

from __future__ import annotations

import asyncio
from itertools import groupby
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import pytest
from contract import accepted, document_state, objects, problem


def notebook_path(notebook):
    return f"/notebooks/{quote(notebook['id'], safe='')}"


def require(notebook, *operations: str):
    missing = set(operations) - set(notebook["operations"])
    if missing:
        pytest.skip(f"notebook does not offer {', '.join(sorted(missing))}")


def live(frame, key):
    assert frame.id, "live event has no cursor"
    message = frame.message()
    assert message.get("time"), "live event has no timestamp"
    assert message.get("request_id") == key, "event has the wrong request_id"
    return message


async def test_required_operations(catalog, pytestconfig):
    available = set(objects(catalog, "host")[0]["operations"])
    assert set(pytestconfig.getoption("--require-operation")) <= available


@pytest.mark.parametrize("authorization", ["", "Bearer wrong-token"])
async def test_security_token(host, authorization):
    response = await host.request(
        "GET", "/events", headers={"Authorization": authorization}
    )
    problem(response, 401, "unauthorized")


async def test_security_cookie(host, record):
    response = await host.request(
        "GET",
        "/events",
        headers={"Authorization": "", "Cookie": f"token={record['token']}"},
    )
    problem(response, 401, "unauthorized")


async def test_security_cors(host):
    response = await host.request(
        "OPTIONS",
        "/events",
        headers={
            "Origin": "https://example.invalid",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert "access-control-allow-origin" not in response.headers
    async with host.watch(
        headers={"Origin": "https://example.invalid"}
    ) as watch:
        await watch.ready()


async def test_unknown_route(host):
    problem(
        await host.request("GET", "/conformance-missing-route"),
        404,
        "not-found",
    )


async def test_catalog_snapshot(catalog):
    events = [frame for frame in catalog if frame.comment is None]
    assert events[0].event == "host"
    assert events[-1].event == "ready"
    assert events[-1].id
    assert len(objects(catalog, "host")) == 1
    projects, notebooks = set(), set()
    for frame in events[:-1]:
        assert frame.id is None, "snapshot event has an id"
        message = frame.message()
        if frame.event == "project":
            projects.add(message["project"]["id"])
        elif frame.event == "notebook":
            notebook = message["notebook"]
            assert notebook["project_id"] in projects
            notebooks.add(notebook["id"])
        elif frame.event in ("runtime", "attachment"):
            assert message[frame.event]["notebook_id"] in notebooks


async def test_stream_types_filter(host):
    snapshot = await host.snapshot(params={"types": "runtime"})
    assert {frame.event for frame in snapshot if frame.comment is None} <= {
        "runtime",
        "ready",
    }


async def test_stream_resume(host, catalog):
    cursor = catalog[-1].id
    resumed = await host.snapshot(headers={"Last-Event-ID": cursor})
    events = [frame for frame in resumed if frame.comment is None]
    assert events[-1].id
    if events[0].event == "reset":
        assert events[0].id is None
        assert all(frame.id is None for frame in events[1:-1])
        assert events[1].event == "host"
    else:
        assert all(frame.id for frame in events), (
            "resume sent a snapshot without reset"
        )


async def test_stream_ping(host, pytestconfig):
    if not pytestconfig.getoption("--slow"):
        pytest.skip("pass --slow to wait for idle pings")
    # Filter out attachments caused by other stream checks.
    async with host.watch(params={"types": "host"}, timeout=20) as watch:
        await watch.ready()
        watch.timeout = 20
        await watch.until(lambda frame: frame.comment == "ping")


async def test_notebook_document(host, catalog):
    notebooks = objects(catalog, "notebook")
    if not notebooks:
        pytest.skip("host has no notebooks")
    path = notebook_path(notebooks[0])
    snapshot = await host.snapshot(path + "/events")
    document_state(snapshot)
    assert objects(snapshot, "attachment"), "notebook stream has no attachment"
    filtered = await host.snapshot(
        path + "/events", params={"types": "cell,document"}
    )
    assert {f.event for f in filtered if f.comment is None} <= {
        "cell",
        "document",
        "ready",
    }
    document_state(filtered)


async def test_create_duplicate_replay_and_missing_key(host, scratch):
    body = {key: scratch[key] for key in ("project_id", "name")}
    if scratch["path"] is not None:
        body["path"] = scratch["path"]
        problem(
            await host.request("POST", "/notebooks", json=body),
            409,
            "conflict",
        )
    problem(
        await host.request("POST", "/notebooks", key="", json=body),
        400,
        "invalid-request",
    )
    # Replay a mutation of our scratch notebook, so cleanup always owns it.
    require(scratch, "notebook.update")
    key = uuid4().hex
    path = notebook_path(scratch)
    first = await host.request(
        "PATCH", path, key=key, json={"name": "conformance-renamed"}
    )
    second = await host.request(
        "PATCH", path, key=key, json={"name": "conformance-renamed"}
    )
    assert accepted(first, 200, "Notebook") == accepted(
        second, 200, "Notebook"
    )
    problem(
        await host.request("PATCH", path, key=key, json={"name": "different"}),
        409,
        "conflict",
    )


def put(cell_id, code, base_etag=None):
    return {
        "kind": "put_cell",
        "base_etag": base_etag,
        "cell": {"id": cell_id, "code": code},
    }


async def edit(host, path, changes, **kwargs: Any):
    return await host.request(
        "POST", path + "/edits", json={"changes": changes}, **kwargs
    )


async def test_edit_atomicity_and_conflicts(host, scratch):
    require(scratch, "notebook.edit")
    path = notebook_path(scratch)
    key = uuid4().hex
    async with host.watch(path + "/events") as watch:
        await watch.ready()
        answer = accepted(
            await edit(host, path, [put("check_a", "x = 1")], key=key),
            200,
            "EditResponse",
        )
        events = await watch.until(lambda f: f.event == "document")
        correlated = [f for f in events if f.comment is None]
        assert [f.event for f in correlated] == ["cell", "document"]
        for frame in correlated:
            live(frame, key)
        assert correlated[-1].message()["document"] == answer["document"]
        assert (
            answer["cells"]["check_a"]["etag"]
            == correlated[0].message()["cell"]["etag"]
        )
    before, cells = document_state(await host.snapshot(path + "/events"))
    # A valid change followed by a stale one must apply neither.
    response = await edit(
        host, path, [put("check_b", "y = 2"), put("check_a", "x = 3", "stale")]
    )
    conflict = problem(response, 409, "conflict")["edit"]
    assert conflict["change"] == 1
    assert conflict["cell"] == cells["check_a"]
    after, after_cells = document_state(await host.snapshot(path + "/events"))
    assert (after, after_cells) == (before, cells)
    problem(
        await edit(
            host, path, [{"kind": "set_order", "base_etag": "*", "order": []}]
        ),
        400,
        "invalid-request",
    )
    assert document_state(await host.snapshot(path + "/events")) == (
        before,
        cells,
    )


async def test_concurrent_edits(host, scratch):
    require(scratch, "notebook.edit")
    path = notebook_path(scratch)
    responses = await asyncio.gather(
        edit(host, path, [put("check_a", "x = 1")]),
        edit(host, path, [put("check_b", "y = 2")]),
    )
    for response in responses:
        accepted(response, 200, "EditResponse")
    _, cells = document_state(await host.snapshot(path + "/events"))
    assert {"check_a", "check_b"} <= cells.keys()


async def test_save(host, scratch):
    require(scratch, "notebook.edit", "notebook.save")
    path = notebook_path(scratch)
    answer = accepted(
        await edit(host, path, [put("check_a", "x = 1")]), 200, "EditResponse"
    )
    response = await host.request(
        "POST",
        path + "/save",
        json={},
        headers={"If-Match": answer["document"]["etag"]},
    )
    saved = accepted(response, 200, "EditResponse")["document"]
    assert saved["saved_etag"] == saved["etag"]
    problem(
        await host.request(
            "POST", path + "/save", json={}, headers={"If-Match": "stale"}
        ),
        409,
        "conflict",
    )


async def test_no_runtime(host, scratch):
    require(scratch, "runtime.run")
    problem(
        await host.request(
            "POST",
            notebook_path(scratch) + "/runtime/runs",
            json={"code": "1"},
        ),
        409,
        "no-runtime",
    )


async def start(host, path, watch):
    key = uuid4().hex
    response = await host.request("PUT", path + "/runtime", json={}, key=key)
    if response.status_code == 409 and response.json().get(
        "type", ""
    ).endswith("decision-required"):
        pytest.skip("runtime requires a user decision")
    runtime = accepted(response, 202, "Runtime")
    assert runtime["status"] == "starting"
    events = await watch.until(
        lambda f: (
            f.event == "runtime"
            and f.message()["runtime"]["id"] == runtime["id"]
            and f.message()["runtime"]["status"] in ("running", "failed")
        )
    )
    assert events[-1].message()["runtime"]["status"] == "running"
    live(events[-1], key)
    return runtime


async def finish_run(watch, run, key, outcome):
    events = await watch.until(
        lambda f: (
            f.event == "run"
            and f.message()["run"]["id"] == run["id"]
            and f.message()["run"]["status"] == "completed"
        )
    )
    executions = {}
    for frame in events:
        if frame.event == "execution":
            execution = frame.message()["execution"]
            if execution["run_id"] == run["id"]:
                live(frame, key)
                executions[execution["id"]] = execution
    assert executions, "run completed without executions"
    assert all(
        e["status"] == "completed" and e["outcome"] is not None
        for e in executions.values()
    ), "run completed before its executions"
    assert live(events[-1], key)["run"]["outcome"] == outcome
    return events, list(executions.values())


@pytest.mark.parametrize(
    ("code", "outcome", "kind"),
    [
        ('print("conformance")', "succeeded", "value"),
        ("raise RuntimeError('conformance')", "failed", "error"),
    ],
)
async def test_run(host, scratch, code, outcome, kind):
    require(scratch, "runtime.start", "runtime.stop", "runtime.run")
    path = notebook_path(scratch)
    async with host.watch(path + "/events") as watch:
        await watch.ready()
        await start(host, path, watch)
        key = uuid4().hex
        run = accepted(
            await host.request(
                "POST", path + "/runtime/runs", json={"code": code}, key=key
            ),
            202,
            "Run",
        )
        assert run["status"] in ("queued", "running")
        assert run["id"] != key
        events, executions = await finish_run(watch, run, key, outcome)
        assert all(
            e["code"] == code and e["cell_id"] is None for e in executions
        )
        assert executions[-1]["outcome"]["kind"] == kind
        if kind == "value":
            assert "conformance" in "".join(
                item["text"] for item in objects(events, "console")
            )
        replay = accepted(
            await host.request(
                "POST", path + "/runtime/runs", json={"code": code}, key=key
            ),
            202,
            "Run",
        )
        assert replay["id"] == run["id"]
        assert replay["status"] == "completed"


async def test_runtime_lifecycle(host, scratch):
    require(scratch, "runtime.start", "runtime.stop", "runtime.restart")
    path = notebook_path(scratch)
    async with host.watch(path + "/events") as watch:
        await watch.ready()
        runtime = await start(host, path, watch)
        existing = accepted(
            await host.request("PUT", path + "/runtime", json={}),
            200,
            "Runtime",
        )
        assert existing["id"] == runtime["id"]
        problem(await host.request("DELETE", path), 409, "conflict")
        key = uuid4().hex
        replacement = accepted(
            await host.request("POST", path + "/runtime/restart", key=key),
            202,
            "Runtime",
        )
        assert replacement["id"] != runtime["id"]
        assert replacement["status"] == "starting"
        events = await watch.until(
            lambda f: (
                f.event == "runtime"
                and f.message()["runtime"]["id"] == replacement["id"]
                and f.message()["runtime"]["status"] in ("running", "failed")
            )
        )
        restart_events = [
            frame
            for frame in events
            if frame.event in ("runtime", "runtime.removed")
            and frame.message().get("request_id") == key
        ]
        transitions = [
            (f.event, f.message().get("runtime", {}).get("status"))
            for f in restart_events
        ]
        assert [transition for transition, _ in groupby(transitions)] == [
            ("runtime", "terminating"),
            ("runtime.removed", None),
            ("runtime", "starting"),
            ("runtime", "running"),
        ]
        for frame in restart_events:
            live(frame, key)
        key = uuid4().hex
        accepted(
            await host.request("DELETE", path + "/runtime", key=key),
            202,
            "Runtime",
        )
        events = await watch.until(lambda f: f.event == "runtime.removed")
        assert live(events[-1], key)["id"] == replacement["id"]


async def test_run_cells(host, scratch):
    require(
        scratch,
        "notebook.edit",
        "runtime.start",
        "runtime.stop",
        "runtime.run",
    )
    path = notebook_path(scratch)
    answer = accepted(
        await edit(host, path, [put("check_a", "x = 1")]), 200, "EditResponse"
    )
    async with host.watch(path + "/events") as watch:
        await watch.ready()
        await start(host, path, watch)
        key = uuid4().hex
        run = accepted(
            await host.request(
                "POST",
                path + "/runtime/runs",
                key=key,
                json={
                    "cells": [
                        {
                            "id": "check_a",
                            "code_hash": answer["cells"]["check_a"][
                                "code_hash"
                            ],
                        }
                    ]
                },
            ),
            202,
            "Run",
        )
        _, executions = await finish_run(watch, run, key, "succeeded")
        assert any(
            e["cell_id"] == "check_a" and e["code"] is None for e in executions
        )
        response = await host.request(
            "POST",
            path + "/runtime/runs",
            json={"cells": [{"id": "check_a", "code_hash": "stale"}]},
        )
        conflict = problem(response, 409, "conflict")["edit"]
        assert conflict["change"] == 0
        assert conflict["cell"] is not None, (
            "run lost the cell from the document"
        )
        assert conflict["cell"]["id"] == "check_a"


async def test_run_conflict_and_interruption(host, scratch):
    require(scratch, "runtime.start", "runtime.stop", "runtime.run")
    path = notebook_path(scratch)
    async with host.watch(path + "/events") as watch:
        await watch.ready()
        await start(host, path, watch)
        key = uuid4().hex
        run = accepted(
            await host.request(
                "POST",
                path + "/runtime/runs",
                key=key,
                json={"code": "import time\ntime.sleep(60)"},
            ),
            202,
            "Run",
        )
        await watch.until(
            lambda f: (
                f.event == "run"
                and f.message()["run"]["id"] == run["id"]
                and f.message()["run"]["status"] == "running"
            )
        )
        problem(
            await host.request(
                "POST", path + "/runtime/runs", json={"code": "pass"}
            ),
            409,
            "conflict",
        )
        endpoint = path + "/runtime/runs/" + quote(run["id"], safe="")
        accepted(await host.request("DELETE", endpoint), 202, "Run")
        _, executions = await finish_run(watch, run, key, "interrupted")
        assert all(e["outcome"]["kind"] == "interrupted" for e in executions)
        problem(await host.request("DELETE", endpoint), 409, "conflict")
