# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import csv
import io

import pytest

from marimo._plugins.ui._impl.tables.utils import get_table_manager


@pytest.mark.parametrize("backend", ["default", "pandas", "polars"])
@pytest.mark.parametrize("separator", [",", ";", "\t"])
@pytest.mark.parametrize("decimal_comma", [False, True])
def test_csv_decimal_separator(
    backend: str, separator: str, decimal_comma: bool
) -> None:
    data = {
        "amount": [3.1416, -1234.5],
        "count": [1, 2],
        "text": ["3.14", "a,b"],
    }
    if backend != "default":
        library = pytest.importorskip(backend)
        data = library.DataFrame(data)
    manager = get_table_manager(data)
    output = manager.to_csv(
        separator=separator, decimal_comma=decimal_comma
    ).decode()
    rows = list(csv.reader(io.StringIO(output), delimiter=separator))
    assert rows == [
        ["amount", "count", "text"],
        ["3,1416" if decimal_comma else "3.1416", "1", "3.14"],
        ["-1234,5" if decimal_comma else "-1234.5", "2", "a,b"],
    ]
    if decimal_comma and separator == ",":
        assert '"3,1416"' in output
    if not decimal_comma:
        assert output == manager.to_csv(separator=separator).decode()
