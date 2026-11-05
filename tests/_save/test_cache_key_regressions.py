# Copyright 2026 Marimo. All rights reserved.
"""Cache keys preserve distinctions observable by notebook code."""

from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from marimo._runtime.commands import ExecuteCellCommand
from marimo._save.encode import deterministic_dumps
from marimo._save.hash import hash_raw_module, hash_wrapped_functions
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


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("x=1", 'x="1"'),
        ("x=1; y=23", "x=12; y=3"),
        ("f=lambda: 1", "def f():\n    return 1"),
    ],
    ids=["constant-type", "constant-boundaries", "lambda-vs-def"],
)
def test_distinct_code_has_distinct_hash(before: str, after: str) -> None:
    assert hash_raw_module(ast.parse(before)) != hash_raw_module(
        ast.parse(after)
    )


def test_bound_builtin_receiver_distinguishes_hash() -> None:
    assert hash_wrapped_functions([1].copy) != hash_wrapped_functions([2].copy)


def test_bound_builtin_unpicklable_receiver_raises(tmp_path: Path) -> None:
    with open(tmp_path / "f", "w") as fh:  # noqa: PTH123
        with pytest.raises(TypeError):
            hash_wrapped_functions(fh.write)


def _one() -> int:
    return 1


def _two() -> int:
    return 2


def test_callable_default_fingerprinted_by_content() -> None:
    def defaults(fn: Any) -> bytes:
        return deterministic_dumps(
            (fn.__defaults__, fn.__kwdefaults__), "sha256"
        )

    def op_one(cb: Any = _one) -> int:
        return cb()

    def op_two(cb: Any = _two) -> int:
        return cb()

    def op_one_again(cb: Any = _one) -> int:
        return cb()

    assert defaults(op_one) == defaults(op_one_again)
    assert defaults(op_one) != defaults(op_two)


def test_closure_values_fingerprinted() -> None:
    def make(n: int) -> Any:
        def callback() -> int:
            return n

        return callback

    assert deterministic_dumps(make(1), "sha256") == deterministic_dumps(
        make(1), "sha256"
    )
    assert deterministic_dumps(make(1), "sha256") != deterministic_dumps(
        make(2), "sha256"
    )


def test_self_referential_closure_terminates() -> None:
    def make() -> Any:
        def recurse(n: int) -> int:
            return n if n == 0 else recurse(n - 1)

        return recurse

    assert deterministic_dumps(make(), "sha256") == deterministic_dumps(
        make(), "sha256"
    )


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


async def test_persistent_block_literal_type_edit(tmp_path: Path) -> None:
    # A right-hand literal other than 1 keeps the int from being deduplicated
    # with the constant 1 in the same code object, which hides the collision.
    def block(literal: str) -> str:
        return (
            f"with mo.persistent_cache('k', save_path={str(tmp_path)!r}):\n"
            f"    x = {literal}\n"
            "    y = x * 2"
        )

    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [command(0, "import marimo as mo"), command(1, block("1"))]
        )
        assert k.globals["y"] == 2
        await k.run([command(1, block('"1"'))])
        assert k.globals["y"] == "11"


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


async def test_bound_builtin_receiver_edit_invalidates() -> None:
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, "op=[1].copy"),
                command(2, "@mo.cache\ndef f():\n    return op()\nresult=f()"),
            ]
        )
        assert k.globals["result"] == [1]
        await k.run([command(1, "op=[2].copy")])
        assert k.globals["result"] == [2]


async def test_helper_default_encoding_error_uses_producer() -> None:
    # A default that pickle cannot encode for a reason other than
    # PicklingError/TypeError (here, recursion depth) must not abort the call.
    deep = "functools.reduce(lambda a, _: [a], range(5000), 0)"
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import functools\nimport marimo as mo"),
                command(1, f"def operation(x={deep}):\n    return 1"),
                command(
                    2,
                    "@mo.cache\ndef f():\n    return operation()\nresult=f()",
                ),
            ]
        )
        assert k.globals.get("result") == 1
        await k.run([command(1, f"def operation(x={deep}):\n    return 2")])
        assert k.globals["result"] == 2


async def test_lambda_helper_default_edit_invalidates() -> None:
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
