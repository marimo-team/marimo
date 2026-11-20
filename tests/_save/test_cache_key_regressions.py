# Copyright 2026 Marimo. All rights reserved.
"""Cache keys preserve distinctions observable by notebook code."""

from __future__ import annotations

from typing import Any

import pytest

from marimo._runtime.commands import ExecuteCellCommand
from marimo._types.ids import CellId_t
from tests._runtime._helpers.session import mocked_kernel_session


def command(cell_id: int, code: str) -> ExecuteCellCommand:
    return ExecuteCellCommand(cell_id=CellId_t(str(cell_id)), code=code)


@pytest.mark.parametrize(
    ("before", "after", "expression", "expected"),
    [
        pytest.param(
            "np.zeros(1,dtype='int64')",
            "np.zeros(1,dtype='float64')",
            "str(x.dtype)",
            "float64",
            marks=pytest.mark.requires("numpy"),
        ),
        pytest.param(
            "np.arange(6).reshape(2,3)",
            "np.arange(6).reshape(2,1,3)",
            "x.shape",
            (2, 1, 3),
            marks=pytest.mark.requires("numpy"),
        ),
        pytest.param(
            "np.arange(4).reshape(2,2)",
            "np.arange(4).reshape(2,2).T",
            "x.tolist()",
            [[0, 2], [1, 3]],
            marks=pytest.mark.requires("numpy"),
        ),
        ("True", "1", "type(x).__name__", "int"),
        pytest.param(
            "np.int64(2)",
            "bytes(2)",
            "type(x).__name__",
            "bytes",
            marks=pytest.mark.requires("numpy"),
        ),
        pytest.param(
            "np.int64(2)",
            "np.int32(2)",
            "type(x).__name__",
            "int32",
            marks=pytest.mark.requires("numpy"),
        ),
        ("{'a':1,'b':2}", "{'b':2,'a':1}", "list(x)", ["b", "a"]),
    ],
    ids=[
        "array-dtype",
        "array-shape",
        "array-transpose",
        "bool-int",
        "numpy-scalar-bytes",
        "numpy-scalar-width",
        "dict-order",
    ],
)
async def test_argument_change_invalidates(
    before: str, after: str, expression: str, expected: Any
) -> None:
    imports = "import marimo as mo"
    if "np." in before or "np." in after:
        imports += "\nimport numpy as np"
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, imports),
                command(1, f"x={before}"),
                command(
                    2,
                    f"@mo.cache\ndef f(x):\n    return {expression}\nresult=f(x)",
                ),
            ]
        )
        assert "result" in k.globals
        await k.run([command(1, f"x={after}")])
        assert k.globals["result"] == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2**64", "int"),
        ("1j", "complex"),
        ("{1:1,'a':2}", "dict"),
        ("{1,'a'}", "set"),
    ],
    ids=["large-int", "complex", "mixed-dict-keys", "mixed-set"],
)
async def test_valid_python_arguments_remain_callable(
    value: str, expected: str
) -> None:
    with mocked_kernel_session() as tk:
        await tk.kernel.run(
            [
                command(0, "import marimo as mo"),
                command(
                    1,
                    f"@mo.cache\ndef f(x):\n    return type(x).__name__\nresult=f({value})",
                ),
            ]
        )
        assert tk.kernel.globals.get("result") == expected
