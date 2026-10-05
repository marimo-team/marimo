# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec

from marimo._host import protocol

# A hand copy of host-protocol/fixtures/record.json in the marimo-desktop
# repository, which generates `protocol.py`. Keep the two in step.
RECORD = (
    b'{"version": 1, "process": {"pid": 12345, "started_at":'
    b' "2026-10-01T09:13:58Z"}, "name": "marimo",'
    b' "url": "http://127.0.0.1:2718/api/marimo/v1", "token": "opaque-token"}'
)


def test_host_record_decodes_the_contract_fixture() -> None:
    record = msgspec.json.decode(RECORD, type=protocol.HostRecord)

    assert record.version == 1
    assert record.process.pid == 12345
    assert record.url == "http://127.0.0.1:2718/api/marimo/v1"
    assert record.token == "opaque-token"


def test_omitted_and_null_fields_stay_distinct() -> None:
    def as_json(value: msgspec.Struct) -> object:
        return msgspec.json.decode(msgspec.json.encode(value))

    assert as_json(protocol.RemovedMessage(id="a1")) == {"id": "a1"}
    assert as_json(protocol.StartRuntimeRequest()) == {}
    project = protocol.Project(
        id="p1", name="scratch", root=None, status="indexed", message=None
    )
    assert as_json(project) == {
        "id": "p1",
        "name": "scratch",
        "root": None,
        "status": "indexed",
        "message": None,
    }
