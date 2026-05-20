# Copyright 2026 Marimo. All rights reserved.
"""Unit tests for ``marimo._runtime.exceptions.unwrap_user_exception``.

Covers the graph-aware ``NameError → MarimoMissingRefError`` upgrade and
the ``NameError.name is None`` guard. Constructing ``NameError("name 'x'
is not defined")`` does NOT set ``.name == "x"`` — only interpreter-raised
NameErrors carry ``.name``. Tests set ``.name`` explicitly.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from marimo._runtime.exceptions import (
    MarimoMissingRefError,
    MarimoRuntimeException,
    unwrap_user_exception,
)


def _wrap(cause: BaseException) -> MarimoRuntimeException:
    """Build a ``MarimoRuntimeException`` with ``__cause__`` set."""
    try:
        raise MarimoRuntimeException from cause
    except MarimoRuntimeException as exc:
        return exc


def _graph(definitions: set[str]) -> Any:
    """Minimal graph stub with only the attribute ``unwrap`` reads."""
    return SimpleNamespace(definitions=definitions)


def test_unwrap_no_graph_returns_raw_cause() -> None:
    cause = ValueError("boom")
    wrapped = _wrap(cause)

    assert unwrap_user_exception(wrapped) is cause


def test_unwrap_nameerror_without_graph_unchanged() -> None:
    """No graph → upgrade never fires, even for NameError."""
    cause = NameError("name 'x' is not defined")
    cause.name = "x"  # set explicitly; constructor doesn't.
    wrapped = _wrap(cause)

    assert unwrap_user_exception(wrapped) is cause


def test_unwrap_nameerror_with_graph_upgrades_when_in_definitions() -> None:
    cause = NameError("name 'x' is not defined")
    cause.name = "x"
    wrapped = _wrap(cause)

    unwrapped = unwrap_user_exception(wrapped, graph=_graph({"x"}))

    assert isinstance(unwrapped, MarimoMissingRefError)
    assert unwrapped.ref == "x"
    assert unwrapped.name_error is cause


def test_unwrap_nameerror_with_graph_passthrough_when_not_in_definitions() -> (
    None
):
    """``.name`` is set but the graph doesn't define it — no upgrade."""
    cause = NameError("name 'x' is not defined")
    cause.name = "x"
    wrapped = _wrap(cause)

    assert unwrap_user_exception(wrapped, graph=_graph(set())) is cause


def test_unwrap_nameerror_with_none_name_returns_raw() -> None:
    """``NameError.name is None`` (the constructor default) → upgrade
    short-circuits via the ``if name and …`` guard."""
    cause = NameError("name 'x' is not defined")
    # Don't set ``.name`` — leave it as the constructor's default
    # (None on most CPython versions). The guard must not upgrade.
    assert getattr(cause, "name", None) is None
    wrapped = _wrap(cause)

    # Even with ``x`` in graph.definitions, the guard prevents upgrade.
    assert unwrap_user_exception(wrapped, graph=_graph({"x"})) is cause


def test_unwrap_no_cause_returns_none() -> None:
    """``MarimoRuntimeException`` raised without ``from …`` has no cause."""
    wrapped = MarimoRuntimeException()

    assert unwrap_user_exception(wrapped) is None
