# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json

from marimo._dataflow.protocol import (
    HeartbeatEvent,
    Kind,
    RunEvent,
    VarErrorEvent,
    VarEvent,
    encode_event,
)


class TestEncodeEvent:
    def test_run_event_started(self) -> None:
        e = RunEvent(run_id="abc", status="started")
        payload = json.loads(encode_event(e))
        assert payload == {
            "type": "run",
            "run_id": "abc",
            "status": "started",
            "elapsed_ms": None,
        }

    def test_run_event_done(self) -> None:
        e = RunEvent(run_id="abc", status="done", elapsed_ms=42.5)
        payload = json.loads(encode_event(e))
        assert payload["status"] == "done"
        assert payload["elapsed_ms"] == 42.5

    def test_var_event(self) -> None:
        e = VarEvent(
            name="result",
            kind=Kind.INTEGER,
            encoding="json",
            run_id="r1",
            seq=1,
            value=42,
        )
        payload = json.loads(encode_event(e))
        assert payload["type"] == "var"
        assert payload["name"] == "result"
        assert payload["kind"] == "integer"
        assert payload["value"] == 42
        assert payload["ref"] is None

    def test_var_error_event(self) -> None:
        e = VarErrorEvent(name="x", run_id="r1", error="NameError: x")
        payload = json.loads(encode_event(e))
        assert payload["type"] == "var-error"
        assert payload["error"] == "NameError: x"

    def test_heartbeat(self) -> None:
        e = HeartbeatEvent(timestamp=1234.5)
        payload = json.loads(encode_event(e))
        assert payload["type"] == "heartbeat"
        assert payload["timestamp"] == 1234.5
