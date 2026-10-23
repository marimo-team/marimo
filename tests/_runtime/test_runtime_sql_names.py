# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._ast.sql_visitor import SQLRef
from marimo._ast.visitor import VariableData
from marimo._runtime.sql_cleanup import in_memory_relation_path


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        (["sales"], ("memory", "main", "sales")),
        (["finance", "sales"], ("memory", "finance", "sales")),
        (
            ["finance", "reports", "sales"],
            ("memory", "finance", "reports", "sales"),
        ),
        (
            ["memory", "finance", "reports", "sales"],
            ("memory", "finance", "reports", "sales"),
        ),
        (["finance.reports", "sales"], ("memory", "finance.reports", "sales")),
        (["attached", "sales"], None),
        (["attached", "finance", "reports", "sales"], None),
    ],
)
def test_in_memory_sql_object_paths(
    parts: list[str], expected: tuple[str, ...] | None
) -> None:
    variable = VariableData("table", sql_ref=SQLRef.from_parts(parts))
    assert (
        in_memory_relation_path(
            variable, parts[-1], frozenset({"memory", "attached"})
        )
        == expected
    )
