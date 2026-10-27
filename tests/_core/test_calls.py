# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, get_args, get_type_hints

import msgspec
import pytest

from marimo._core import calls, protocol
from marimo._core.calls import (
    CALLS,
    InterruptCall,
    MutationHeaders,
    OperationCall,
    RunParams,
)
from marimo._core.operations import NotebookBridge
from protocols.host.generate import compose

NOTEBOOK = protocol.NotebookId("n1")


def test_calls_decode_from_request_parts() -> None:
    def decode(**parts: object) -> OperationCall:
        return msgspec.json.decode(
            msgspec.json.encode(parts), type=OperationCall
        )

    headers = {"idempotency-key": "k", "authorization": "Bearer t"}
    assert decode(
        operation="runtime.interrupt",
        params={"notebook_id": "n1", "run_id": "r1"},
        headers=headers,
    ) == InterruptCall(
        RunParams(NOTEBOOK, protocol.RunId("r1")), MutationHeaders("k")
    )
    for invalid in (
        {"operation": "runtime.interrupt", "params": {"notebook_id": "n1"}},
        {"operation": "notebook.missing", "params": {"notebook_id": "n1"}},
    ):
        with pytest.raises(msgspec.ValidationError):
            decode(**invalid, headers=headers)


def test_calls_match_the_spec() -> None:
    document = compose()

    def resolve(value: dict[str, Any]) -> dict[str, Any]:
        if "$ref" not in value:
            return value
        target = document
        for part in value["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        return target

    def schema_name(content: dict[str, Any]) -> str:
        reference: str = content["application/json"]["schema"]["$ref"]
        return reference.rsplit("/", 1)[1]

    def names(kind: type[msgspec.Struct]) -> set[str]:
        return {field.encode_name for field in msgspec.structs.fields(kind)}

    specified = {
        operation["operationId"]: (method.upper(), path, item, operation)
        for path, item in document["paths"].items()
        for method, operation in item.items()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert set(get_args(OperationCall)) == set(CALLS)
    assert {kind.__struct_config__.tag for kind in CALLS} == {
        operation_id
        for operation_id in specified
        if operation_id.startswith("runtime.")
        or operation_id in {"notebook.edit", "notebook.save"}
    }

    for kind in CALLS:
        method, path, item, operation = specified[
            str(kind.__struct_config__.tag)
        ]
        assert (kind.METHOD, kind.PATH) == (method, path)

        parameters = [
            resolve(parameter)
            for parameter in [
                *item.get("parameters", []),
                *operation.get("parameters", []),
            ]
        ]
        fields = {field.name: field for field in msgspec.structs.fields(kind)}
        assert names(fields["params"].type) == {
            parameter["name"]
            for parameter in parameters
            if parameter["in"] == "path"
        }
        assert names(fields["headers"].type) == {
            parameter["name"].lower()
            for parameter in parameters
            if parameter["in"] == "header"
        }
        body = operation.get("requestBody")
        if body is None:
            assert set(fields) == {"params", "headers"}
        else:
            assert set(fields) == {"params", "headers", "body"}
            assert fields["body"].type.__name__ == schema_name(
                resolve(body)["content"]
            )

        hints = get_type_hints(
            kind.handle, {**vars(calls), "NotebookBridge": NotebookBridge}
        )
        statuses, response = get_args(hints["return"])
        success = {
            int(status): resolve(value)
            for status, value in operation["responses"].items()
            if status.startswith("2")
        }
        assert set(get_args(statuses)) == set(success)
        for value in success.values():
            assert schema_name(value["content"]) == response.__name__
