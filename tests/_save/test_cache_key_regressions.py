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


async def test_private_helper_edit_invalidates() -> None:
    # An underscore name is cell-local, so the helper, the cached function,
    # and the call share a cell. The compiled name is mangled; the source is
    # not.
    def cell(value: int) -> str:
        return (
            f"def _helper():\n    return {value}\n"
            "@mo.cache\ndef f(cb):\n    return _helper() + cb()\n"
            "result=f(_helper)"
        )

    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run([command(0, "import marimo as mo"), command(1, cell(1))])
        assert k.globals["result"] == 2
        await k.run([command(1, cell(2))])
        assert k.globals["result"] == 4


async def test_multiline_string_edit_invalidates() -> None:
    def helper(literal: str) -> str:
        return f"def helper():\n    return {literal}"

    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, helper("'''a\n  \nb'''")),
                command(
                    2, "@mo.cache\ndef f():\n    return helper()\nresult=f()"
                ),
            ]
        )
        assert k.globals["result"] == "a\n  \nb"
        await k.run([command(1, helper("'''a\n\nb'''"))])
        assert k.globals["result"] == "a\n\nb"


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("container", [False, True])
async def test_closure_value_edit_invalidates(
    wrapped: bool, container: bool
) -> None:
    make = (
        "import functools\n"
        "def make(n):\n"
        "    def inner():\n"
        "        return n\n"
        + (
            "    @functools.wraps(inner)\n"
            "    def outer():\n"
            "        return inner()\n"
            "    return outer"
            if wrapped
            else "    return inner"
        )
    )
    arg, call = ("[cb]", "cbs[0]()") if container else ("cb", "cbs()")
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, make),
                command(2, "cb = make(1)"),
                command(
                    3,
                    f"@mo.cache\ndef f(cbs):\n    return {call}\nresult=f({arg})",
                ),
            ]
        )
        assert k.globals["result"] == 1
        await k.run([command(2, "cb = make(2)")])
        assert k.globals["result"] == 2


async def test_lambdas_sharing_a_line_remain_callable() -> None:
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, "a, b = lambda: 1, lambda: 2"),
                command(
                    2,
                    "@mo.cache\ndef f(cb):\n    return cb()\nr1=f(a)\nr2=f(b)",
                ),
            ]
        )
        assert (k.globals.get("r1"), k.globals.get("r2")) == (1, 2)


async def test_identical_source_in_different_modules(tmp_path: Path) -> None:
    for name, value in (("m_one", 1), ("m_two", 2)):
        (tmp_path / f"{name}.py").write_text(
            f"VALUE = {value}\n\n\ndef callback():\n    return VALUE\n"
        )
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(
                    0,
                    "import sys\nimport marimo as mo\n"
                    f"sys.path.insert(0, {str(tmp_path)!r})\n"
                    "import m_one\nimport m_two",
                ),
                command(
                    1,
                    "@mo.cache\ndef f(cbs):\n    return cbs[0]()\n"
                    "r1=f([m_one.callback])\nr2=f([m_two.callback])",
                ),
            ]
        )
        assert (k.globals.get("r1"), k.globals.get("r2")) == (1, 2)


async def test_reloaded_module_function_invalidates(tmp_path: Path) -> None:
    module = tmp_path / "reloaded.py"

    def write(value: int) -> None:
        module.write_text(f"def cb():\n    return {value}\n")

    write(1)
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(
                    0,
                    "import importlib\nimport sys\nimport marimo as mo\n"
                    f"sys.path.insert(0, {str(tmp_path)!r})\n"
                    "import reloaded",
                ),
                command(
                    1,
                    "@mo.cache\ndef f(cb):\n    return cb()\nr=f(reloaded.cb)",
                ),
            ]
        )
        assert k.globals["r"] == 1
        # A different size: the import system keys a stale .pyc on the
        # source's size and whole-second mtime.
        write(100)
        await k.run(
            [
                command(
                    1,
                    "importlib.reload(reloaded)\n"
                    "@mo.cache\ndef f(cb):\n    return cb()\nr=f(reloaded.cb)",
                )
            ]
        )
        assert k.globals["r"] == 100


async def test_source_less_callback_remains_callable() -> None:
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, "cb = eval('lambda: 7')"),
                command(2, "@mo.cache\ndef f(cb):\n    return cb()\nr=f(cb)"),
            ]
        )
        assert k.globals.get("r") == 7
        await k.run([command(1, "cb = eval('lambda: 8')")])
        assert k.globals["r"] == 8


async def test_nested_lambda_edit_invalidates() -> None:
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, "cb = lambda: (lambda: 3)"),
                command(
                    2, "@mo.cache\ndef f(cb):\n    return cb()()\nr=f(cb)"
                ),
            ]
        )
        assert k.globals.get("r") == 3
        await k.run([command(1, "cb = lambda: (lambda: 4)")])
        assert k.globals["r"] == 4


def test_set_of_functions_keyed_by_member_content() -> None:
    def one() -> int:
        return 1

    def two() -> int:
        return 2

    assert deterministic_dumps({one}, "sha256") != deterministic_dumps(
        {two}, "sha256"
    )


class _Node:
    def __init__(self) -> None:
        self.children: set[_Node] = set()


def test_set_back_reference_terminates() -> None:
    node = _Node()
    node.children.add(node)
    assert isinstance(deterministic_dumps(node, "sha256"), bytes)


async def test_nested_lambda_depth_edit_invalidates() -> None:
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, "cb = lambda: lambda: lambda: 3"),
                command(
                    2,
                    "@mo.cache\ndef f(cb):\n    return type(cb()()).__name__\n"
                    "r=f(cb)",
                ),
            ]
        )
        assert k.globals.get("r") == "function"
        await k.run([command(1, "cb = lambda: lambda: 3")])
        assert k.globals["r"] == "int"


def test_source_less_set_constants() -> None:
    strings = eval("lambda x: x in {'a', 'b'}")  # noqa: S307
    assert isinstance(hash_wrapped_functions(strings), bytes)
    ints = eval("lambda x: x in {65, 66}")  # noqa: S307
    raw = eval("lambda x: x in b'AB'")  # noqa: S307
    assert hash_wrapped_functions(ints) != hash_wrapped_functions(raw)


async def test_callback_capturing_a_module_remains_callable() -> None:
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(
                    1,
                    "def make():\n    import math\n"
                    "    def cb(x):\n        return math.sqrt(x)\n"
                    "    return cb\ncb = make()",
                ),
                command(2, "@mo.cache\ndef f(cb):\n    return cb(4)\nr=f(cb)"),
            ]
        )
        assert k.globals.get("r") == 2.0


def test_shared_set_references_are_observable() -> None:
    shared = {1}
    assert deterministic_dumps((shared, shared), "sha256") != (
        deterministic_dumps((shared, shared.copy()), "sha256")
    )


def test_restored_function_stub_keeps_its_hash(tmp_path: Path) -> None:
    from marimo._save.stubs.function_stub import FunctionStub

    module = tmp_path / "stubbed.py"
    module.write_text("x = 1\n\n\ndef helper():\n    return 1\n")
    namespace: dict[str, Any] = {}
    exec(  # noqa: S102
        compile(module.read_text(), str(module), "exec", dont_inherit=True),
        namespace,
    )
    helper = namespace["helper"]
    restored = FunctionStub(helper).load({})
    assert hash_wrapped_functions(restored) == hash_wrapped_functions(helper)


async def test_folded_nested_lambda_remains_callable() -> None:
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, "cb = lambda: True or (lambda: 2)"),
                command(2, "@mo.cache\ndef f(cb):\n    return cb()\nr=f(cb)"),
            ]
        )
        assert k.globals.get("r") is True


def test_nested_sets_encode_linearly(monkeypatch: pytest.MonkeyPatch) -> None:
    from marimo._save import encode

    calls = 0
    original = encode.deterministic_dumps

    def counting(*args: Any, **kwargs: Any) -> bytes:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(encode, "deterministic_dumps", counting)
    value: frozenset[Any] = frozenset()
    for _ in range(12):
        value = frozenset({value})
    counting(value, "sha256")
    assert calls < 40


def test_cell_local_helper_hash_is_cell_independent() -> None:
    from marimo._ast.compiler import compile_cell

    def helper(cell_id: str) -> Any:
        cell = compile_cell(
            "def _helper():\n    return 1", cell_id=CellId_t(cell_id)
        )
        namespace: dict[str, Any] = {}
        exec(cell.body, namespace)  # noqa: S102
        return next(v for k, v in namespace.items() if k.endswith("helper"))

    assert hash_wrapped_functions(helper("abcd")) == hash_wrapped_functions(
        helper("wxyz")
    )


def test_restored_stub_without_its_file_keeps_its_hash() -> None:
    import linecache

    from marimo._ast.compiler import compile_cell
    from marimo._save.stubs.function_stub import FunctionStub

    cell = compile_cell(
        "x = 1\n\n\ndef helper():\n    return 1", cell_id=CellId_t("stub-one")
    )
    namespace: dict[str, Any] = {}
    exec(cell.body, namespace)  # noqa: S102
    helper = namespace["helper"]
    before = hash_wrapped_functions(helper)
    stub = FunctionStub(helper)
    # Another kernel process has no linecache entry for this cell file.
    linecache.cache.pop(helper.__code__.co_filename, None)
    assert hash_wrapped_functions(stub.load({})) == before


def test_revisited_callback_keeps_its_identity() -> None:
    def a() -> int:
        return 1

    def b() -> int:
        return 2

    def h(x: Any = a, y: Any = b) -> int:
        return x() + y()

    assert deterministic_dumps([h, a], "sha256") != deterministic_dumps(
        [h, b], "sha256"
    )


async def test_unencodable_default_keeps_source_identity() -> None:
    def operation(value: int) -> str:
        return (
            "import threading\n"
            f"def operation(lock=threading.Lock()):\n    return {value}"
        )

    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, operation(1)),
                command(
                    2, "@mo.cache\ndef f(op):\n    return op()\nr=f(operation)"
                ),
            ]
        )
        assert k.globals.get("r") == 1
        await k.run([command(1, operation(2))])
        assert k.globals["r"] == 2


def test_set_member_aliases_with_surroundings_are_observable() -> None:
    a, b = _Node(), _Node()
    assert deterministic_dumps(({a}, a), "sha256") != deterministic_dumps(
        ({a}, b), "sha256"
    )


def test_two_restored_stubs_from_one_cell_keep_their_hashes() -> None:
    import linecache

    from marimo._ast.compiler import compile_cell
    from marimo._save.stubs.function_stub import FunctionStub

    cell = compile_cell(
        "def one():\n    return 1\n\n\ndef two():\n    return 2",
        cell_id=CellId_t("stub-two"),
    )
    namespace: dict[str, Any] = {}
    exec(cell.body, namespace)  # noqa: S102
    one, two = namespace["one"], namespace["two"]
    before = (hash_wrapped_functions(one), hash_wrapped_functions(two))
    stubs = (FunctionStub(one), FunctionStub(two))
    linecache.cache.pop(one.__code__.co_filename, None)
    restored = tuple(stub.load({}) for stub in stubs)
    assert tuple(map(hash_wrapped_functions, restored)) == before


def test_optimize_level_is_part_of_the_key() -> None:
    import subprocess
    import sys

    program = (
        "import ast\nfrom marimo._save.hash import hash_raw_module\n"
        "print(hash_raw_module(ast.parse('x = 1')).hex())"
    )
    plain, optimized = (
        subprocess.run(
            [sys.executable, *flags, "-c", program],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for flags in ((), ("-O",))
    )
    assert plain != optimized


def test_future_import_is_part_of_the_key(tmp_path: Path) -> None:
    import importlib
    import sys

    body = "def f(x: int):\n    return x\n"
    (tmp_path / "plain_future.py").write_text(body)
    (tmp_path / "annotated_future.py").write_text(
        "from __future__ import annotations\n" + body
    )
    sys.path.insert(0, str(tmp_path))
    try:
        plain = importlib.import_module("plain_future").f
        annotated = importlib.import_module("annotated_future").f
    finally:
        sys.path.remove(str(tmp_path))
    assert hash_wrapped_functions(plain) != hash_wrapped_functions(annotated)


def test_restored_factory_helper_keeps_its_hash() -> None:
    import linecache

    from marimo._ast.compiler import compile_cell
    from marimo._save.stubs.function_stub import FunctionStub

    cell = compile_cell(
        "def make():\n    def helper():\n        return 1\n    return helper\n"
        "h = make()",
        cell_id=CellId_t("stub-factory"),
    )
    namespace: dict[str, Any] = {}
    exec(cell.body, namespace)  # noqa: S102
    helper = namespace["h"]
    before = hash_wrapped_functions(helper)
    stub = FunctionStub(helper)
    linecache.cache.pop(helper.__code__.co_filename, None)
    assert hash_wrapped_functions(stub.load({})) == before


def test_zip_imported_function_hashes_by_source(tmp_path: Path) -> None:
    import importlib
    import inspect
    import sys
    import zipfile

    archive = tmp_path / "zipped.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("zipped_module.py", "def f():\n    return 1\n")
    sys.path.insert(0, str(archive))
    try:
        f = importlib.import_module("zipped_module").f
    finally:
        sys.path.remove(str(archive))
    before = hash_wrapped_functions(f)
    inspect.getsource(f)
    assert hash_wrapped_functions(f) == before


def test_library_function_hash_walks_its_module_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    import marimo._save.hash as hash_module

    hash_wrapped_functions(json.dumps)
    walks = 0
    original = hash_module.ast.walk

    def counting(node: Any) -> Any:
        nonlocal walks
        walks += 1
        return original(node)

    monkeypatch.setattr(hash_module.ast, "walk", counting)
    hash_wrapped_functions(json.dumps)
    assert walks == 0


def test_source_less_slice_constant() -> None:
    sliced = eval("lambda x: x[1:3]")  # noqa: S307
    assert isinstance(hash_wrapped_functions(sliced), bytes)


def test_restored_stub_keeps_future_annotations(tmp_path: Path) -> None:
    import importlib
    import sys

    from marimo._save.stubs.function_stub import FunctionStub

    (tmp_path / "future_stub.py").write_text(
        "from __future__ import annotations\n\n\n"
        "def f(x: Missing):\n    return x\n"
    )
    sys.path.insert(0, str(tmp_path))
    try:
        f = importlib.import_module("future_stub").f
    finally:
        sys.path.remove(str(tmp_path))
    # The kernel passes its globals, which carry the module name.
    restored = FunctionStub.from_dump(FunctionStub(f).dump()).load(
        {"__name__": f.__module__}
    )
    assert restored(1) == 1
    assert restored.__annotations__ == {"x": "Missing"}
    assert hash_wrapped_functions(restored) == hash_wrapped_functions(f)


@pytest.mark.parametrize("factory_first", [True, False])
def test_restored_factory_and_helper_keep_their_hashes(
    factory_first: bool,
) -> None:
    import linecache

    from marimo._ast.compiler import compile_cell
    from marimo._save.stubs.function_stub import FunctionStub

    cell = compile_cell(
        "def make():\n    def helper():\n        return 1\n    return helper\n"
        "h = make()",
        cell_id=CellId_t(f"stub-nested-{factory_first}"),
    )
    namespace: dict[str, Any] = {}
    exec(cell.body, namespace)  # noqa: S102
    functions = [namespace["make"], namespace["h"]]
    if not factory_first:
        functions.reverse()
    before = [hash_wrapped_functions(fn) for fn in functions]
    stubs = [FunctionStub(fn) for fn in functions]
    linecache.cache.pop(functions[0].__code__.co_filename, None)
    restored = [stub.load({}) for stub in stubs]
    assert [hash_wrapped_functions(fn) for fn in restored] == before


def test_restored_stub_survives_a_shifted_file(tmp_path: Path) -> None:
    import importlib
    import sys

    from marimo._save.stubs.function_stub import FunctionStub

    module = tmp_path / "shifted.py"
    module.write_text("def f():\n    return 1\n")
    sys.path.insert(0, str(tmp_path))
    try:
        f = importlib.import_module("shifted").f
    finally:
        sys.path.remove(str(tmp_path))
    before = hash_wrapped_functions(f)
    stub = FunctionStub(f)
    module.write_text("# a comment\n" + module.read_text())
    restored = stub.load({"__name__": f.__module__})
    assert hash_wrapped_functions(restored) == before
