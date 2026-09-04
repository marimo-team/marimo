# Copyright 2026 Marimo. All rights reserved.
"""Cache keys preserve distinctions observable by notebook code."""

from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.watch._directory import DirectoryState
from marimo._save.encode import deterministic_dumps
from marimo._save.hash import hash_raw_module
from marimo._save.loaders.lazy import LazyLoader
from marimo._save.signing import CacheSigner, generate_keypair
from marimo._save.stores.file import FileStore
from marimo._types.ids import CellId_t
from tests._runtime._helpers.session import mocked_kernel_session

if TYPE_CHECKING:
    from pathlib import Path


def command(cell_id: int, code: str) -> ExecuteCellCommand:
    return ExecuteCellCommand(cell_id=CellId_t(str(cell_id)), code=code)


@pytest.mark.parametrize(
    ("before", "after"),
    [("x=1", 'x="1"'), ("x=1; y=23", "x=12; y=3")],
    ids=["constant-type", "constant-boundaries"],
)
def test_distinct_code_has_distinct_hash(before: str, after: str) -> None:
    assert hash_raw_module(ast.parse(before)) != hash_raw_module(
        ast.parse(after)
    )


@pytest.mark.requires("numpy")
@pytest.mark.parametrize("change", ["dtype", "shape", "transpose"])
def test_pickled_array_preserves_metadata(change: str) -> None:
    import numpy as np

    before = np.arange(4, dtype=np.int64).reshape(2, 2)
    if change == "dtype":
        after = before.view(np.float64)
    elif change == "shape":
        after = before.reshape(2, 1, 2)
    else:
        after = before.T
    assert deterministic_dumps(before, "sha256") != deterministic_dumps(
        after, "sha256"
    )


def test_directory_walk_returns_entries(tmp_path: Path) -> None:
    (tmp_path / "added.txt").write_text("x")
    state = DirectoryState(tmp_path)
    entries = list(state.walk())
    assert [(str(root), dirs, files) for root, dirs, files in entries] == [
        (str(tmp_path), [], ["added.txt"])
    ]


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
        ("{'a':1,'b':2}", "{'b':2,'a':1}", "list(x)", ["b", "a"]),
    ],
    ids=[
        "array-dtype",
        "array-shape",
        "array-transpose",
        "bool-int",
        "numpy-scalar-bytes",
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


async def test_cached_function_literal_type_edit() -> None:
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, "@mo.cache\ndef f():\n    return 1\nresult=f()"),
            ]
        )
        assert k.globals["result"] == 1
        await k.run(
            [command(1, '@mo.cache\ndef f():\n    return "1"\nresult=f()')]
        )
        assert k.globals["result"] == "1"


@pytest.mark.parametrize("parameter", ["x", "*, x"])
async def test_helper_default_edit_invalidates(parameter: str) -> None:
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, f"def operation({parameter}=1):\n    return x"),
                command(
                    2,
                    "@mo.cache\ndef f():\n    return operation()\nresult=f()",
                ),
            ]
        )
        assert k.globals["result"] == 1
        await k.run(
            [command(1, f"def operation({parameter}=2):\n    return x")]
        )
        assert k.globals["result"] == 2


async def test_unpicklable_helper_default_uses_producer() -> None:
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(
                    1,
                    "def operation(callback=lambda: 1):\n    return callback()",
                ),
                command(
                    2,
                    "@mo.cache\ndef f():\n    return operation()\nresult=f()",
                ),
            ]
        )
        assert k.globals.get("result") == 1
        await k.run(
            [
                command(
                    1,
                    "def operation(callback=lambda: 2):\n    return callback()",
                )
            ]
        )
        assert k.globals["result"] == 2


@pytest.mark.parametrize(
    "imports",
    ["import {module} as operation", "from {module} import sqrt as operation"],
)
async def test_module_alias_edit_invalidates_with_pinning(
    imports: str,
) -> None:
    call = (
        "operation.sqrt(x)"
        if imports.startswith("import ")
        else "operation(x)"
    )
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(
                    0, "import marimo as mo\n" + imports.format(module="math")
                ),
                command(
                    1,
                    f"@mo.cache(pin_modules=True)\ndef f(x):\n    return {call}\nresult=f(4)",
                ),
            ]
        )
        assert type(k.globals["result"]) is float
        await k.run(
            [
                command(
                    0, "import marimo as mo\n" + imports.format(module="cmath")
                )
            ]
        )
        assert type(k.globals["result"]) is complex


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2**64", "int"), ("1j", "complex"), ("{1:1,'a':2}", "dict")],
    ids=["large-int", "complex", "mixed-dict-keys"],
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


async def test_watched_directory_change_invalidates(tmp_path: Path) -> None:
    body = "@mo.cache\ndef f(d):\n    return sorted(p.name for p in d.iterdir())\nresult=f(directory)"
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, f"directory=mo.watch.directory({str(tmp_path)!r})"),
                command(2, body),
            ]
        )
        assert k.globals["result"] == []
        (tmp_path / "added.txt").write_text("x")
        # Run the consumer without waiting for the watcher.
        await k.run([command(2, body)])
        assert k.globals["result"] == ["added.txt"]


@pytest.mark.requires("cryptography")
async def test_signed_automatic_cell_cache_invalidates(tmp_path: Path) -> None:
    signer = CacheSigner.from_private_key_pem(generate_keypair()[0])
    original_init = LazyLoader.__init__
    loaders: list[LazyLoader] = []

    def init(loader: LazyLoader, *args: Any, **kwargs: Any) -> None:
        kwargs.update(store=FileStore(str(tmp_path)), signer=signer)
        original_init(loader, *args, **kwargs)
        loaders.append(loader)

    with patch.object(LazyLoader, "__init__", init):
        with mocked_kernel_session() as tk:
            k = tk.kernel
            k.user_config = copy.deepcopy(k.user_config)
            k.user_config["runtime"]["cache_cells"] = True
            await k.run([command(0, "x=1")])
            assert k.globals["x"] == 1
            for loader in loaders:
                loader.flush()
            await k.run([command(0, 'x="1"')])
            assert k.globals["x"] == "1"
