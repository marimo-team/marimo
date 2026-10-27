# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import importlib
from datetime import datetime
from pathlib import Path

import msgspec
import msgspec.yaml
import pytest

from marimo._core import protocol
from protocols.host.generate import event_adapters, tuple_arrays


@pytest.mark.parametrize(
    "annotation",
    [
        'Annotated[list[str], Meta(description="résumé")]',
        'Annotated[list[str], Meta(description="日本語 🐍")]',
        'Annotated[\n        list[str],\n        Meta(description="résumé"),\n    ]',
    ],
)
def test_unicode_array_annotation_preserves_following_fields(
    annotation: str,
) -> None:
    source = f"""\
# Generated model — preserve Unicode before and within annotations.
from typing import Annotated
from msgspec import Meta, Struct

class Example(Struct, frozen=True):
    xs: {annotation}
    value: str
    rows: list[list[int]]
"""
    namespace = {}
    compiled = compile(
        tuple_arrays(source.encode("utf-8")),
        "<generated>",
        "exec",
        dont_inherit=True,
    )
    exec(compiled, namespace)
    value = msgspec.json.decode(
        b'{"xs": ["a"], "value": "after", "rows": [[1, 2]]}',
        type=namespace["Example"],
    )
    assert value.xs == ("a",)
    assert value.value == "after"
    assert value.rows == ((1, 2),)


def test_event_adapters_follow_schema_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Record access does not depend on names matching the wire tag."""
    document = msgspec.yaml.decode(
        Path("protocols/host/openapi.yaml").read_bytes()
    )
    schemas = document["components"]["schemas"]
    message = schemas.pop("ProjectMessage")
    message["properties"]["workspace"] = message["properties"].pop("project")
    message["required"] = ["workspace"]
    schemas["WorkspaceUpdate"] = message
    event = schemas.pop("ProjectEvent")
    event["properties"]["data"]["$ref"] = (
        "#/components/schemas/WorkspaceUpdate"
    )
    schemas["WorkspaceChanged"] = event
    schemas["Event"]["discriminator"]["mapping"]["project"] = (
        "#/components/schemas/WorkspaceChanged"
    )
    update_type = msgspec.defstruct(
        "WorkspaceUpdate",
        [
            ("workspace", protocol.Project),
            ("request_id", str | msgspec.UnsetType, msgspec.UNSET),
            ("time", datetime | msgspec.UnsetType, msgspec.UNSET),
        ],
    )
    event_type = msgspec.defstruct("WorkspaceChanged", [("data", update_type)])
    monkeypatch.setattr(
        protocol, "WorkspaceUpdate", update_type, raising=False
    )
    monkeypatch.setattr(
        protocol, "WorkspaceChanged", event_type, raising=False
    )
    namespace = {}
    exec(compile(event_adapters(document), "<adapters>", "exec"), namespace)
    project = protocol.Project(
        id=protocol.ProjectId("p1"),
        name="project",
        root="/tmp",
        message=None,
        operations=(),
        status="ready",
    )
    wrapped = namespace["record"](project)
    assert wrapped == event_type(update_type(project))
    assert namespace["body"](wrapped) is project
    assert namespace["removed"](protocol.Project, project.id) == (
        protocol.ProjectRemovedEvent(protocol.RemovedMessage(id="p1"))
    )


def test_event_adapters_use_adjacent_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "generated_protocol"
    package.mkdir()
    (package / "protocol.py").write_bytes(Path(protocol.__file__).read_bytes())
    document = msgspec.yaml.decode(
        Path("protocols/host/openapi.yaml").read_bytes()
    )
    (package / "protocol_events.py").write_text(
        event_adapters(document, relative_import=True), encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    models = importlib.import_module("generated_protocol.protocol")
    events = importlib.import_module("generated_protocol.protocol_events")
    cell = msgspec.json.decode(
        Path("protocols/host/fixtures/cell.json").read_bytes(),
        type=models.Cell,
    )
    assert events.body(events.record(cell)) is cell
    assert events.protocol is models
