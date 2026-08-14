# Copyright 2026 Marimo. All rights reserved.
"""Benchmarks for kernel <-> frontend message serialization.

Every cell output, console message and variable update is encoded to JSON
before it is sent over the websocket, so the encoder is on the hot path of
any notebook that produces output.
"""

from __future__ import annotations

import datetime
import decimal
import uuid
from typing import TYPE_CHECKING, Any

from marimo._messaging.msgspec_encoder import encode_json_bytes

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture


def _build_payload(n_rows: int) -> dict[str, Any]:
    """A payload shaped like a table/dataframe cell output."""
    return {
        "op": "cell-op",
        "cell_id": "Hbol",
        "status": "idle",
        "timestamp": 1_700_000_000.0,
        "output": {
            "channel": "output",
            "mimetype": "application/vnd.marimo+mimebundle",
            "data": [
                {
                    "id": index,
                    "name": f"row-{index}",
                    "created_at": datetime.datetime(2024, 1, 1)
                    + datetime.timedelta(days=index),
                    "amount": decimal.Decimal(f"{index}.25"),
                    "uid": uuid.UUID(int=index),
                    "tags": [f"tag-{index % 7}", f"tag-{index % 11}"],
                    "nested": {"a": index, "b": [index, index + 1]},
                }
                for index in range(n_rows)
            ],
        },
    }


def test_encode_small_message(benchmark: BenchmarkFixture) -> None:
    payload = _build_payload(10)
    benchmark(encode_json_bytes, payload)


def test_encode_large_message(benchmark: BenchmarkFixture) -> None:
    payload = _build_payload(1000)
    benchmark(encode_json_bytes, payload)
