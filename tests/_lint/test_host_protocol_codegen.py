# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import msgspec
import pytest

from protocols.host.generate import tuple_arrays


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
