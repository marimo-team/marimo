# Copyright 2026 Marimo. All rights reserved.
"""A `@mo.cache` / `@mo.persistent_cache` wrapper survives a cache save/restore
cycle as a *working* wrapper (not an inert tripwire), captured by `FunctionStub`
with `is_cached=True`.

On a cache hit the restored wrapper serves the wrapper's own persistent-cache
entries without re-importing the body's heavy dependencies (the motivating case
is a torch notebook exported to WASM). Only a genuine miss reaches the body.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import marimo as mo
from marimo._ast.transformers import get_hashable_ast
from marimo._save.cache import Cache
from marimo._save.loaders.lazy import from_item, to_item
from marimo._save.stubs import FunctionStub
from marimo._save.stubs.lazy_stub import UnhashableStub

SKIP = {"cache", "persistent_cache"}


def _cache() -> Cache:
    return Cache(
        defs={},
        hash="h",
        cache_type="Pure",
        stateful_refs=set(),
        hit=False,
        meta={},
    )


def _as_notebook(wrapper: Any) -> Any:
    """Cell code runs as `__main__`; mimic that so the convert guard fires."""
    wrapper.__wrapped__.__module__ = "__main__"
    return wrapper


def test_cache_call_converts_to_cached_stub() -> None:
    @mo.cache
    def add(a, b):
        return a + b

    stub = _cache()._convert_to_stub_if_needed(_as_notebook(add))
    assert isinstance(stub, FunctionStub)
    assert stub.is_cached
    assert stub.filename == "<add>"
    # The decorator line is captured so re-exec re-applies it.
    assert "@mo.cache" in stub.code
    assert "def add" in stub.code


def test_async_cache_call_converts_to_cached_stub() -> None:
    @mo.cache
    async def afetch(a):
        return a

    stub = _cache()._convert_to_stub_if_needed(_as_notebook(afetch))
    assert isinstance(stub, FunctionStub)
    assert stub.is_cached
    assert "async def afetch" in stub.code


def test_lambda_wrapper_not_converted() -> None:
    wrapper = _as_notebook(mo.cache(lambda x: x + 1))
    result = _cache()._convert_to_stub_if_needed(wrapper)
    assert not (isinstance(result, FunctionStub) and result.is_cached)


def test_library_module_function_not_converted() -> None:
    # __module__ is the test module (not "__main__"): a library-owned cache
    # wrapper must not be captured as notebook source.
    @mo.cache
    def add(a, b):
        return a + b

    result = _cache()._convert_to_stub_if_needed(add)
    assert not (isinstance(result, FunctionStub) and result.is_cached)


def test_manifest_round_trip() -> None:
    @mo.cache
    def add(a, b):
        return a + b

    stub = _cache()._convert_to_stub_if_needed(_as_notebook(add))
    item = to_item(Path("cache/add"), stub, var_name="add")
    # Inlined in the function field, carrying the is_cached flag.
    assert item.function == (stub.code, stub.filename, stub.lineno, True)
    assert item.reference is None

    back = from_item(item, "add")
    assert isinstance(back, FunctionStub)
    assert back.is_cached
    assert back.code == stub.code
    assert back.filename == "<add>"


def test_load_rebuilds_working_wrapper() -> None:
    @mo.cache
    def add(a, b):
        return a + b

    stub = _cache()._convert_to_stub_if_needed(_as_notebook(add))
    rebuilt = stub.load({"mo": mo})

    # A live cache wrapper, not the stub.
    assert type(rebuilt).__name__ == "_cache_call"
    assert rebuilt(2, 3) == 5
    # Second identical call is served from the wrapper's own cache.
    assert rebuilt(2, 3) == 5
    assert rebuilt.cache_info().hits >= 1


def test_restored_wrapper_hashes_to_same_ast() -> None:
    # The wrapper's own AST is re-hashed after restore to derive per-call keys.
    # The synthetic `<name>` filename + linecache registration must reproduce
    # the native hashable AST even though this function is not at line 1 of the
    # source file (a naive real-filename re-hash would read the wrong lines).
    @mo.persistent_cache(method="lazy")
    def compute(a, b):
        return a + b

    orig_ast = ast.dump(
        get_hashable_ast(compute.__wrapped__, skip_decorators=SKIP)
    )

    stub = FunctionStub(compute, is_cached=True)
    rebuilt = stub.load({"mo": mo})
    restored_ast = ast.dump(
        get_hashable_ast(rebuilt.__wrapped__, skip_decorators=SKIP)
    )

    assert restored_ast == orig_ast


def test_body_ref_degraded_does_not_gate_rebuild() -> None:
    # The regression this design fixes: a cache wrapper resolves its body refs
    # at call time, so a degraded (unavailable) body ref must NOT block the
    # rebuild the way it (correctly) does for a plain function / class. The
    # is_cached flag keeps `_restore_deps` empty for the wrapper, so the
    # degraded-dep gate never fires.
    def heavy(a):  # stands in for a torch-backed helper
        return a * 100

    @mo.cache
    def needy(a):
        return heavy(a)

    cache = _cache()
    stub = cache._convert_to_stub_if_needed(_as_notebook(needy))
    assert isinstance(stub, FunctionStub)
    assert stub.is_cached

    # No cross-def dependency gating for the wrapper.
    assert cache._restore_deps(stub) == set()
    scope = {"heavy": UnhashableStub(var_name="heavy")}
    assert cache._first_degraded_dep(stub, scope) is None
