# Copyright 2026 Marimo. All rights reserved.
"""Generated host models preserve the shared wire examples."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import msgspec
import pytest

from marimo._core import protocol

FIXTURES = (
    Path(__file__).resolve().parents[2] / "protocols" / "host" / "fixtures"
)
MODELS = {
    "record.json": protocol.HostRecord,
    "cell.json": protocol.Cell,
    "analysis.json": protocol.Analysis,
    "diagnostic.json": protocol.Error,
    "edit.json": protocol.EditRequest,
    "edit-conflict-request.json": protocol.EditRequest,
    "edit-response.json": protocol.EditResponse,
    "execution-restored.json": protocol.Execution,
    "run-cells-request.json": protocol.RunRequest,
}


def stream_events(path: Path) -> list[dict[str, str]]:
    """Read the fixtures' SSE framing, rejecting incomplete examples."""
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n\n"), f"{path.name}: unterminated event"
    events = []
    for block in text.split("\n\n"):
        fields = {}
        for line in block.splitlines():
            if line.startswith(":"):
                continue
            key, separator, value = line.partition(": ")
            assert separator, line
            assert key in {"id", "event", "data"}, line
            assert key not in fields, f"duplicate {key}"
            fields[key] = value
        if fields:
            assert {"event", "data"} <= fields.keys()
            events.append(fields)
    assert events, f"{path.name}: no events"
    return events


def identity(body: dict[str, Any]) -> str:
    return body.get("id") or body["notebook_id"]


def messages(name: str, kind: str) -> list[dict[str, Any]]:
    return [
        json.loads(event["data"])
        for event in stream_events(FIXTURES / name)
        if event["event"] == kind
    ]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def assert_content_hashes(value: Any) -> None:
    if isinstance(value, list):
        for child in value:
            assert_content_hashes(child)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in {"etag", "code_hash"} or key.endswith("_etag"):
                if child is not None and child != "*":
                    assert re.fullmatch(r"[0-9a-f]{16}", child), (key, child)
            assert_content_hashes(child)
        if "code_hash" in value and isinstance(value.get("code"), str):
            assert value["code_hash"] == content_hash(value["code"])
        if {"etag", "config", "name", "code_hash"} <= value.keys():
            config = value["config"]
            parts = [
                value["code_hash"],
                value["name"],
                *(
                    canonical_json(config[key])
                    for key in (
                        "column",
                        "disabled",
                        "hide_code",
                        "expand_output",
                    )
                ),
            ]
            assert value["etag"] == content_hash("\n".join(parts))
        if "order_etag" in value:
            assert value["order_etag"] == content_hash(
                canonical_json(value["order"])
            )
            assert value["app_config_etag"] == content_hash(
                canonical_json(value["app_config"])
            )


def assert_immutable(value: object) -> None:
    if isinstance(value, msgspec.Struct):
        for field in msgspec.structs.fields(type(value)):
            child = getattr(value, field.name)
            with pytest.raises(AttributeError):
                setattr(value, field.name, child)
            assert_immutable(child)
    elif isinstance(value, tuple):
        for child in value:
            assert_immutable(child)
    else:
        assert not isinstance(value, list), "protocol arrays must be tuples"


def round_trip(model: type, text: str) -> None:
    wire = json.loads(text)
    assert_content_hashes(wire)
    value = msgspec.json.decode(
        json.dumps({**wire, "future_field": True}), type=model
    )
    assert json.loads(msgspec.json.encode(value)) == wire
    assert_immutable(value)


@pytest.mark.parametrize(
    "path", sorted(FIXTURES.rglob("*.json")), ids=lambda path: path.name
)
def test_json_models(path: Path) -> None:
    model = (
        protocol.Problem
        if path.parent.name == "problems"
        else MODELS[path.name]
    )
    round_trip(model, path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "path", sorted(FIXTURES.glob("*.sse")), ids=lambda path: path.name
)
def test_stream_models(path: Path) -> None:
    events = stream_events(path)
    snapshot = "id" not in events[0]
    cursors = set()
    for event in events:
        kind = event["event"]
        data = json.loads(event["data"])
        if kind in ("ready", "reset"):
            assert data == {}
            assert ("id" in event) == (kind == "ready")
            snapshot = kind == "reset"
            continue
        assert ("id" not in event) == snapshot
        assert ("time" not in data) == snapshot
        if "id" in event:
            assert event["id"] not in cursors
            cursors.add(event["id"])
        model = (
            protocol.RemovedMessage
            if kind.endswith(".removed")
            else getattr(protocol, f"{kind.title()}Message")
        )
        round_trip(model, event["data"])
    assert not snapshot, f"{path.name}: incomplete snapshot"


def test_custom_event_replay_preserves_envelope_and_cursor() -> None:
    live = stream_events(FIXTURES / "custom-events.sse")
    replay = stream_events(FIXTURES / "custom-events-replay.sse")
    assert [event["event"] for event in live] == ["ready", "custom"]
    assert [event["event"] for event in replay] == ["custom", "ready"]
    assert replay[0] == live[1]
    assert replay[1]["id"] == live[1]["id"]


@pytest.mark.parametrize(
    "data",
    [
        None,
        True,
        False,
        0,
        1,
        1.0,
        1.5,
        "hello",
        [1, None],
        {"nested": [False]},
    ],
)
def test_custom_payload_preserves_any_json_value(data: Any) -> None:
    wire = {
        "custom": {
            "type": "example.progress",
            "data": data,
        },
        "time": "2026-10-13T20:00:00Z",
    }
    value = msgspec.json.decode(json.dumps(wire), type=protocol.CustomMessage)
    assert canonical_json(
        json.loads(msgspec.json.encode(value))
    ) == canonical_json(wire)


def test_custom_payload_is_required_even_when_null_is_allowed() -> None:
    with pytest.raises(
        msgspec.ValidationError, match="missing required field `data`"
    ):
        msgspec.json.decode(
            '{"type":"example.progress"}',
            type=protocol.Custom,
        )


def test_catalog_capabilities_and_runtime_stop() -> None:
    catalogs = []
    for name in ("events.sse", "events-reset.sse"):
        state: dict[str, dict[str, Any]] = {}
        host_operations = set(messages(name, "host")[0]["host"]["operations"])
        for event in stream_events(FIXTURES / name):
            kind = event["event"]
            data = json.loads(event["data"])
            if kind in {"host", "ready", "reset"}:
                continue
            if kind.endswith(".removed"):
                del state[kind.removesuffix(".removed")][data["id"]]
                continue
            obj = data[kind]
            if kind in {"project", "notebook"}:
                assert set(obj["operations"]) <= host_operations
                if "runtime.run" in obj["operations"]:
                    assert "runtime.interrupt" in obj["operations"]
            if kind == "notebook":
                assert obj["project_id"] in state["project"]
            if kind in {"runtime", "attachment"}:
                assert obj["notebook_id"] in state["notebook"]
            state.setdefault(kind, {})[identity(obj)] = obj
        assert not state.get("runtime")
        assert set(state["attachment"]) == {"a1", "a2"}
        catalogs.append(
            {kind: objects for kind, objects in state.items() if objects}
        )
    assert catalogs[0] == catalogs[1]
    for notebook in messages("notebook-events.sse", "notebook"):
        assert set(notebook["notebook"]["operations"]) <= host_operations


def test_notebook_snapshot_matches_live_history() -> None:
    live = stream_events(FIXTURES / "run.sse")
    notebook = stream_events(FIXTURES / "notebook-events.sse")
    ready = next(
        i for i, event in enumerate(notebook) if event["event"] == "ready"
    )
    live_by_cursor = {event["id"]: event for event in live}
    for event in notebook[ready + 1 :]:
        assert event == live_by_cursor[event["id"]]

    # Build the state just before the first shared live event. The snapshot
    # must reconstruct that state, not include changes from after its cursor.
    checkpoint = next(
        i
        for i, event in enumerate(live)
        if event["id"] == notebook[ready]["id"]
    )
    state = {}
    for event in live[: checkpoint + 1]:
        kind = event["event"]
        message = json.loads(event["data"])
        message.pop("time")
        state[(kind, identity(message[kind]))] = message
    seen_cells = set()
    for event in notebook[:ready]:
        kind = event["event"]
        message = json.loads(event["data"])
        if kind == "cell":
            seen_cells.add(message["cell"]["id"])
        elif kind == "document":
            assert set(message["document"]["order"]) == seen_cells
        key = (kind, identity(message[kind]))
        if key in state:
            assert state.pop(key) == message
    assert not state

    cells = {
        m["cell"]["id"]: m["cell"]
        for m in messages("notebook-events.sse", "cell")
    }
    document = messages("notebook-events.sse", "document")[0]["document"]
    assert len(document["order"]) == len(set(document["order"]))
    assert set(document["order"]) == cells.keys()
    assert (
        json.loads((FIXTURES / "cell.json").read_text(encoding="utf-8"))
        == cells["c3"]
    )
    assert_document_hash(document, cells)


def assert_document_hash(
    document: dict[str, Any], cells: dict[str, Any]
) -> None:
    parts = [document["order_etag"], document["app_config_etag"]]
    parts.extend(cells[cell_id]["etag"] for cell_id in document["order"])
    assert document["etag"] == content_hash("\n".join(parts))


@pytest.mark.parametrize(
    ("name", "outcome"),
    [
        ("run.sse", "succeeded"),
        ("run-cells.sse", "succeeded"),
        ("run-failed.sse", "failed"),
        ("run-interrupted.sse", "interrupted"),
        ("notebook-events.sse", "succeeded"),
    ],
)
def test_run_lifecycles(name: str, outcome: str) -> None:
    runs: dict[str, Any] = {}
    executions: dict[str, Any] = {}
    request_ids = {}
    for event in stream_events(FIXTURES / name):
        kind = event["event"]
        data = json.loads(event["data"])
        if kind == "run":
            run = data["run"]
            previous = runs.get(run["id"])
            assert previous is None or previous["status"] != "completed"
            assert run["id"] != data["request_id"]
            request_ids[run["id"]] = data["request_id"]
            runs[run["id"]] = run
            assert sum(r["status"] != "completed" for r in runs.values()) <= 1
            if run["status"] == "completed":
                members = [
                    e for e in executions.values() if e["run_id"] == run["id"]
                ]
                assert all(e["status"] == "completed" for e in members)
                assert run["outcome"] == outcome
            else:
                assert run["outcome"] is None
            assert (run["completed_at"] is not None) == (
                run["status"] == "completed"
            )
        elif kind == "execution":
            execution = data["execution"]
            run = runs[execution["run_id"]]
            assert run["status"] != "completed"
            assert data["request_id"] == request_ids[run["id"]]
            assert execution["runtime_id"] == "r1"
            previous = executions.get(execution["id"])
            if previous is not None:
                statuses = ["queued", "running", "completed"]
                assert statuses.index(execution["status"]) >= statuses.index(
                    previous["status"]
                )
                for field in (
                    "run_id",
                    "runtime_id",
                    "cell_id",
                    "code_hash",
                    "caused_by",
                ):
                    assert execution[field] == previous[field]
            if execution["caused_by"] is not None:
                assert (
                    executions[execution["caused_by"]]["run_id"] == run["id"]
                )
            if execution["cell_id"] is None:
                assert execution["code"] is not None
            else:
                assert execution["code"] is None
            if execution["status"] == "queued":
                assert execution["outcome"] is None
                assert execution["started_at"] is None
                assert execution["depends_on"] == {}
            elif previous is not None and previous["status"] != "queued":
                assert execution["depends_on"] == previous["depends_on"]
            for revision in execution["depends_on"].values():
                assert revision is None or revision["update"] >= 0
            if execution["status"] == "completed":
                assert execution["outcome"] is not None
            assert (execution["completed_at"] is not None) == (
                execution["status"] == "completed"
            )
            executions[execution["id"]] = execution
        elif kind in {"console", "display"}:
            assert data[kind]["execution_id"] in executions
        elif kind == "variable":
            variable = data["variable"]
            execution = executions[variable["execution_id"]]
            assert execution["cell_id"] is not None
            if variable["revision"]["update"] == 0:
                # Bound before the execution completes.
                assert execution["status"] == "running"
                assert (
                    variable["revision"]["execution"]
                    == variable["execution_id"]
                )
    assert runs
    assert all(r["status"] == "completed" for r in runs.values())


def test_cell_run_request_and_results() -> None:
    cells = {
        m["cell"]["id"]: m["cell"]
        for m in messages("notebook-events.sse", "cell")
    }
    request = json.loads(
        (FIXTURES / "run-cells-request.json").read_text(encoding="utf-8")
    )
    assert request == {
        "cells": [{"id": "c3", "code_hash": cells["c3"]["code_hash"]}]
    }
    executions = {
        m["execution"]["id"]: m["execution"]
        for m in messages("run-cells.sse", "execution")
    }
    assert cells["c3"]["code"] == "x = 21"
    assert cells["k7f2"]["code"] == "y = x * 2"
    assert executions["e12"]["caused_by"] is None
    assert executions["e13"]["caused_by"] == "e12"
    assert executions["e12"]["depends_on"] == {}
    assert executions["e13"]["depends_on"] == {
        "x": {"execution": "e12", "update": 0}
    }
    for execution in executions.values():
        assert (
            execution["code_hash"] == cells[execution["cell_id"]]["code_hash"]
        )
        assert execution["outcome"] == {"kind": "value", "display": None}
    variables = {
        m["variable"]["name"]: m["variable"]
        for m in messages("run-cells.sse", "variable")
    }
    assert variables == {
        "x": {
            "id": "e12-x",
            "execution_id": "e12",
            "name": "x",
            "revision": {"execution": "e12", "update": 0},
            "type": "int",
            "preview": "21",
        },
        "y": {
            "id": "e13-y",
            "execution_id": "e13",
            "name": "y",
            "revision": {"execution": "e13", "update": 0},
            "type": "int",
            "preview": "42",
        },
    }
    assert not messages("run-cells.sse", "console")


def test_edit_request_response_and_events() -> None:
    cells = {
        m["cell"]["id"]: m["cell"]
        for m in messages("notebook-events.sse", "cell")
    }
    before = messages("notebook-events.sse", "document")[0]["document"]
    request = json.loads((FIXTURES / "edit.json").read_text(encoding="utf-8"))
    response = json.loads(
        (FIXTURES / "edit-response.json").read_text(encoding="utf-8")
    )
    changed = {
        m["cell"]["id"]: m["cell"] for m in messages("edits.sse", "cell")
    }
    order = before["order"].copy()
    touched = {}
    for change in request["changes"]:
        if change["kind"] == "put_cell":
            cell = change["cell"]
            previous = cells.get(cell["id"])
            assert change["base_etag"] == (
                previous["etag"] if previous else None
            )
            if previous is None:
                order.insert(order.index(change["after"]) + 1, cell["id"])
            updated = changed[cell["id"]]
            assert all(updated[key] == value for key, value in cell.items())
            cells[cell["id"]] = updated
            touched[cell["id"]] = {
                key: updated[key] for key in ("etag", "code_hash", "version")
            }
        else:
            assert change["kind"] == "delete_cell"
            assert change["base_etag"] == cells.pop(change["id"])["etag"]
            order.remove(change["id"])
            touched[change["id"]] = None
    assert response["document"]["app_config"] == before["app_config"]
    assert response["document"]["order"] == order
    assert response["cells"] == touched
    assert_document_hash(response["document"], cells)
    applied, saved = messages("edits.sse", "document")
    assert applied["document"] == response["document"]
    assert saved["document"] == {
        **response["document"],
        "saved_etag": response["document"]["etag"],
    }
    events = stream_events(FIXTURES / "edits.sse")
    assert [e["event"] for e in events] == [
        "cell",
        "cell",
        "cell.removed",
        "document",
        "document",
    ]
    assert {json.loads(e["data"])["request_id"] for e in events[:-1]} == {
        applied["request_id"]
    }
    assert messages("edits.sse", "cell.removed")[0]["id"] == "k7f2"

    conflict_request = json.loads(
        (FIXTURES / "edit-conflict-request.json").read_text(encoding="utf-8")
    )
    conflict = json.loads(
        (FIXTURES / "problems/edit-conflict.json").read_text(encoding="utf-8")
    )["edit"]
    assert len(conflict_request["changes"]) == 1
    change = conflict_request["changes"][0]
    assert change["base_etag"] != cells[change["cell"]["id"]]["etag"]
    assert conflict == {
        "change": 0,
        "cell": cells["c3"],
        "document": response["document"],
    }


def test_restored_result_matches_source() -> None:
    source = json.loads((FIXTURES / "cell.json").read_text(encoding="utf-8"))
    restored = json.loads(
        (FIXTURES / "execution-restored.json").read_text(encoding="utf-8")
    )
    assert restored["cell_id"] == source["id"]
    assert restored["code_hash"] == content_hash(source["code"])
    assert restored["run_id"] is None
    assert restored["runtime_id"] is None


@pytest.mark.parametrize(
    "name",
    [
        "AttachmentId",
        "CellId",
        "ExecutionId",
        "ItemId",
        "NotebookId",
        "ProjectId",
        "RunId",
        "RuntimeId",
    ],
)
def test_identifier_constraints(name: str) -> None:
    identifier = getattr(protocol, name)
    assert identifier.__name__ == name
    assert hasattr(identifier, "__supertype__")
    assert msgspec.json.decode(b'"id"', type=identifier) == identifier("id")
    with pytest.raises(msgspec.ValidationError, match="length"):
        msgspec.json.decode(b'""', type=identifier)


@pytest.mark.parametrize("field", ["run_id", "runtime_id", "caused_by"])
def test_required_nullable_fields(field: str) -> None:
    wire = json.loads(
        (FIXTURES / "execution-restored.json").read_text(encoding="utf-8")
    )
    missing = {key: value for key, value in wire.items() if key != field}
    with pytest.raises(
        msgspec.ValidationError, match="missing required field"
    ):
        msgspec.json.decode(json.dumps(missing), type=protocol.Execution)
    with pytest.raises(msgspec.ValidationError, match="length"):
        msgspec.json.decode(
            json.dumps({**wire, field: ""}), type=protocol.Execution
        )
