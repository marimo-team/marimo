from __future__ import annotations

import pytest
import marimo

app = marimo.App()


@pytest.mark.xfail(
    reason=(
        "Invoking a cell is not directly supported, and as such should fail "
        "until #2293. However, the decorated function _should_ be picked up "
        "by pytest. A hook in conftest.py should esnure this."
    ),
    raises=RuntimeError,
    strict=True,
)
@app.cell
def test_cell_is_invoked():
    assert True
