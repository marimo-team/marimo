# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec
import pytest

from marimo._core import protocol

api = protocol.api
NOTEBOOK = protocol.NotebookId("n1")


def test_calls_decode_from_request_parts() -> None:
    def decode(**parts: object) -> api.Call:
        call: api.Call = msgspec.json.decode(
            msgspec.json.encode(parts), type=api.Call
        )
        return call

    headers = {"idempotency-key": "k", "authorization": "Bearer t"}
    assert decode(
        operation="runtime.cancel",
        params={"notebook_id": "n1", "run_id": "r1"},
        headers=headers,
    ) == api.Notebook.Cancel.Call(
        api.Notebook.Cancel.Params(NOTEBOOK, protocol.RunId("r1")),
        api.Notebook.Cancel.Headers("k"),
    )
    assert decode(
        operation="runtime.interrupt",
        params={"notebook_id": "n1"},
        headers=headers,
    ) == api.Notebook.Interrupt.Call(
        api.Notebook.Interrupt.Params(NOTEBOOK),
        api.Notebook.Interrupt.Headers("k"),
    )
    for invalid in (
        {"operation": "runtime.cancel", "params": {"notebook_id": "n1"}},
        {"operation": "notebook.missing", "params": {"notebook_id": "n1"}},
    ):
        with pytest.raises(msgspec.ValidationError):
            decode(**invalid, headers=headers)


@pytest.mark.parametrize(
    ("operation", "body"),
    [
        ("runtime.run", {"code": "1"}),
        ("runtime.run", {"cells": []}),
        ("runtime.run", {"cells": [{"id": "c1"}], "code": "1"}),
        ("runtime.execute", {"cells": [{"id": "c1"}]}),
        ("runtime.execute", {"code": "1", "cells": [{"id": "c1"}]}),
    ],
)
def test_execution_calls_reject_the_other_operations_payload(operation, body):
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(
            {
                "operation": operation,
                "params": {"notebook_id": "n1"},
                "headers": {"idempotency-key": "k"},
                "body": body,
            },
            api.Call,
        )
