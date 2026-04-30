# Copyright 2026 Marimo. All rights reserved.
"""Dataflow wire protocol — the closed event union and schema types.

This module is deliberately separate from marimo._messaging.notification.
The two protocols have different consumers, lifecycles, and stability
guarantees. This one is meant to be implementable in ~200 lines by any
language.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

import msgspec

# ---------------------------------------------------------------------------
# Kind — closed type system for variables
# ---------------------------------------------------------------------------


class Kind(str, Enum):
    """Closed set of logical types for dataflow variables."""

    NULL = "null"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    BYTES = "bytes"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"
    DURATION = "duration"
    LIST = "list"
    DICT = "dict"
    TUPLE = "tuple"
    OPTIONAL = "optional"
    UNION = "union"
    TABLE = "table"
    TENSOR = "tensor"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    HTML = "html"
    PDF = "pdf"
    UI_ELEMENT = "ui_element"
    ANY = "any"


# ---------------------------------------------------------------------------
# Schema types
# ---------------------------------------------------------------------------


class InputSchema(msgspec.Struct, rename="camel"):
    """Describes one input to the dataflow graph."""

    name: str
    kind: Kind = Kind.ANY
    default: Any | None = None
    description: str | None = None
    required: bool = True
    # Kind-specific constraints (min, max, options, arrow_schema_b64, etc.)
    constraints: dict[str, Any] | None = None


class OutputSchema(msgspec.Struct, rename="camel"):
    """Describes one output variable."""

    name: str
    kind: Kind = Kind.ANY
    description: str | None = None
    # Wire encodings the server can produce for this variable
    accepts: list[str] | None = None


class TriggerSchema(msgspec.Struct, rename="camel"):
    """Describes a named side-effect that can be invoked explicitly."""

    name: str
    description: str | None = None


class DataflowSchema(msgspec.Struct, rename="camel"):
    """Full schema for a dataflow-mode notebook."""

    inputs: list[InputSchema]
    outputs: list[OutputSchema]
    triggers: list[TriggerSchema]
    schema_id: str


# ---------------------------------------------------------------------------
# Events — the outbound SSE union
# ---------------------------------------------------------------------------


class SchemaEvent(msgspec.Struct, tag="schema", tag_field="type"):
    schema: DataflowSchema
    schema_id: str


class SchemaChangedEvent(
    msgspec.Struct, tag="schema-changed", tag_field="type"
):
    schema_id: str


class RunEvent(msgspec.Struct, tag="run", tag_field="type"):
    run_id: str
    status: Literal["started", "done"]
    elapsed_ms: float | None = None


class SupersededEvent(msgspec.Struct, tag="superseded", tag_field="type"):
    run_id: str


class VarEvent(msgspec.Struct, tag="var", tag_field="type"):
    name: str
    kind: Kind
    encoding: str
    run_id: str
    seq: int
    value: Any | None = None
    ref: str | None = None


class VarErrorEvent(msgspec.Struct, tag="var-error", tag_field="type"):
    name: str
    run_id: str
    error: str
    traceback: str | None = None


class TriggerResultEvent(
    msgspec.Struct, tag="trigger-result", tag_field="type"
):
    name: str
    run_id: str
    status: Literal["ok", "error"]
    error: str | None = None


class HeartbeatEvent(msgspec.Struct, tag="heartbeat", tag_field="type"):
    timestamp: float


DataflowEvent = (
    SchemaEvent
    | SchemaChangedEvent
    | RunEvent
    | SupersededEvent
    | VarEvent
    | VarErrorEvent
    | TriggerResultEvent
    | HeartbeatEvent
)


# Encoder for SSE serialization
_encoder = msgspec.json.Encoder()


def encode_event(event: DataflowEvent) -> bytes:
    """Serialize a DataflowEvent to JSON bytes."""
    return _encoder.encode(event)
