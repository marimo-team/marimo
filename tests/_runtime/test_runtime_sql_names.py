# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._ast.sql_visitor import SQLRef
from marimo._ast.visitor import VariableData
from marimo._runtime.runtime import _in_memory_qualified_name


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        (["sales"], '"memory"."main"."sales"'),
        (["finance", "sales"], '"memory"."finance"."sales"'),
        (
            ["finance", "reports", "sales"],
            '"memory"."finance"."reports"."sales"',
        ),
        (
            ["memory", "finance", "reports", "sales"],
            '"memory"."finance"."reports"."sales"',
        ),
        (["finance.reports", "sales"], '"memory"."finance.reports"."sales"'),
        (["attached", "sales"], None),
        (["attached", "finance", "reports", "sales"], None),
    ],
)
def test_in_memory_sql_object_paths(
    parts: list[str], expected: str | None
) -> None:
    variable = VariableData("table", sql_ref=SQLRef.from_parts(parts))
    assert (
        _in_memory_qualified_name(
            variable, parts[-1], lambda: {"memory", "attached"}
        )
        == expected
    )
