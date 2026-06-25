# Copyright 2026 Marimo. All rights reserved.
"""UnhashableStub semantics: data, tripwire, and Cache.restore handling.

Split from the cached-lifecycle suite: these tests exercise only the
stub serialization toolkit (no runtime lifecycle involvement).
"""

from __future__ import annotations

import pickle

import pytest

from marimo._runtime.exceptions import (
    MarimoCancelCellError,
    MarimoUnhashableCacheError,
)
from marimo._save.cache import Cache
from marimo._save.stubs.lazy_stub import UnhashableStub

# ---------------------------------------------------------------------------
# UnhashableStub: data + tripwire semantics
# ---------------------------------------------------------------------------


class TestUnhashableStub:
    def test_init_captures_type_info(self) -> None:
        stub = UnhashableStub(
            lambda x: x, var_name="f", error_msg="lambdas not pickleable"
        )
        assert stub.var_name == "f"
        assert "function" in stub.type_name.lower()
        assert stub.error_msg == "lambdas not pickleable"

    def test_load_raises_unhashable_error(self) -> None:
        stub = UnhashableStub(None, var_name="f", error_msg="cannot pickle")
        with pytest.raises(MarimoUnhashableCacheError) as exc_info:
            stub.load({})
        assert "f" in exc_info.value.variables
        assert "cannot pickle" in exc_info.value.error_details

    def test_inherits_cancel_cell_parent(self) -> None:
        """MarimoUnhashableCacheError funnels through the parent class
        in the runner's classifier."""
        err = MarimoUnhashableCacheError(
            cells_to_rerun=set(), variables=[], error_details=""
        )
        assert isinstance(err, MarimoCancelCellError)

    def test_pickle_roundtrip(self) -> None:
        original = UnhashableStub(None, var_name="f", error_msg="oops")
        original.type_name = "builtins.function"
        round_tripped = pickle.loads(pickle.dumps(original))
        assert round_tripped.var_name == "f"
        assert round_tripped.type_name == "builtins.function"
        assert round_tripped.error_msg == "oops"

    def test_isinstance_works(self) -> None:
        """Tripwires must not interfere with isinstance — the restore
        path uses isinstance to decide whether to install the marker."""
        stub = UnhashableStub(None, var_name="f")
        assert isinstance(stub, UnhashableStub)

    def test_repr_does_not_trip(self) -> None:
        """repr is safe to invoke for debugging / logging."""
        stub = UnhashableStub(None, var_name="f", error_msg="oops")
        stub.type_name = "builtins.function"
        text = repr(stub)
        assert "UnhashableStub" in text
        assert "f" in text


class TestUnhashableStubTripwire:
    """`__call__` is the only tripwire (see UnhashableStub docstring).

    Other accesses deliberately fall through to Python defaults so
    framework probes (`getattr(value, "_repr_mimebundle_", None)`,
    `isinstance`, `hasattr`, storage-engine introspection, etc.) stay
    inert and don't cancel innocent cells.
    """

    def _stub(self) -> UnhashableStub:
        return UnhashableStub(None, var_name="x", error_msg="cannot pickle")

    def test_call_trips(self) -> None:
        with pytest.raises(MarimoUnhashableCacheError) as ei:
            self._stub()(42)
        assert ei.value.variables == ["x"]

    def test_getattr_does_not_trip(self) -> None:
        # Falls through to Python's default: a missing attribute raises
        # AttributeError, not the cache tripwire.
        with pytest.raises(AttributeError):
            _ = self._stub().some_method

    def test_len_does_not_trip(self) -> None:
        with pytest.raises(TypeError):
            len(self._stub())

    def test_iter_does_not_trip(self) -> None:
        with pytest.raises(TypeError):
            list(self._stub())

    def test_internal_attrs_dont_trip(self) -> None:
        """var_name / type_name / error_msg / load / to_bytes are
        intentionally accessible — pickling and the runner's classifier
        rely on them."""
        s = self._stub()
        assert s.var_name == "x"
        assert s.type_name == "<unknown>"
        assert s.error_msg == "cannot pickle"
        # load() raises (by design); just confirm the method is reachable.
        with pytest.raises(MarimoUnhashableCacheError):
            s.load({})
        # to_bytes() pickles successfully.
        assert s.to_bytes() == pickle.dumps(s)


# ---------------------------------------------------------------------------
# Cache.restore — total-restore semantics for UnhashableStub
# ---------------------------------------------------------------------------


class TestRestoreUnhashableMarker:
    def test_top_level_marker_preserved(self) -> None:
        """UnhashableStub at the top level of defs is placed in scope as-is,
        not loaded (which would raise)."""
        stub = UnhashableStub(None, var_name="f", error_msg="cannot pickle")
        cache = Cache(
            defs={"f": stub},
            hash="h",
            cache_type="ExecutionPath",
            stateful_refs=set(),
            hit=True,
            meta={},
        )
        scope: dict[str, object] = {}
        cache.restore(scope)
        assert isinstance(scope["f"], UnhashableStub)

    def test_nested_marker_in_container_preserved(self) -> None:
        """UnhashableStub nested in tuple/list/dict survives the recursive
        restore unchanged — the marker propagates instead of triggering
        `.load()` (which raises)."""
        stub = UnhashableStub(None, var_name="g", error_msg="cannot pickle")
        cache = Cache(
            defs={
                "in_tuple": (1, stub, 3),
                "in_list": [stub, "x"],
                "in_dict": {"k": stub},
            },
            hash="h",
            cache_type="ExecutionPath",
            stateful_refs=set(),
            hit=True,
            meta={},
        )
        scope: dict[str, object] = {}
        cache.restore(scope)
        assert scope["in_tuple"][1] is stub  # type: ignore[index]
        assert scope["in_list"][0] is stub  # type: ignore[index]
        assert scope["in_dict"]["k"] is stub  # type: ignore[index]
