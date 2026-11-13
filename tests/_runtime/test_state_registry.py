# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc
import weakref
from typing import TYPE_CHECKING

import pytest

from marimo._runtime.context import get_context
from marimo._runtime.state import State, StateRegistry

if TYPE_CHECKING:
    from marimo._runtime.runtime import Kernel
    from tests.conftest import ExecReqProvider


def test_retain_active_aliases() -> None:
    registry = StateRegistry()
    value = State(0, _registry=registry, _name="value")
    registry.register(value, "alias", context="file")

    registry.retain_active_states({"alias"})

    assert registry.lookup("value") is None
    assert registry.lookup("alias", context="file") is value
    assert registry.bound_names(value) == {"file:alias"}


def test_rebinding_removes_only_previous_name() -> None:
    registry = StateRegistry()
    previous = State(0, _registry=registry, _name="value")
    registry.register(previous, "alias")
    current = State(1, _registry=registry, _name="value")

    assert registry.lookup("value") is current
    assert registry.lookup("alias") is previous
    assert registry.bound_names(previous) == {"alias"}
    assert registry.bound_names(current) == {"value"}


def test_collected_state_does_not_remove_replacement() -> None:
    registry = StateRegistry()
    previous = State(0, _registry=registry, _name="value")
    registry.register(previous, "value")
    previous_ref = weakref.ref(previous)
    current = State(1, _registry=registry, _name="value")

    del previous
    gc.collect()

    assert previous_ref() is None
    assert registry.lookup("value") is current
    assert registry.bound_names(current) == {"value"}


@pytest.mark.parametrize("context", [None, "file"])
def test_delete_preserves_other_aliases(context: str | None) -> None:
    registry = StateRegistry()
    value = State(0, _registry=registry, _name="value", _context=context)
    registry.register(value, "alias")

    registry.delete("value", value, context=context)

    assert registry.lookup("value", context=context) is None
    assert registry.lookup("alias") is value
    assert registry.bound_names(value) == {"alias"}


def test_delete_does_not_remove_another_state() -> None:
    registry = StateRegistry()
    previous = State(0, _registry=registry, _name="value")
    current = State(1, _registry=registry, _name="value")

    registry.delete("value", previous)

    assert registry.lookup("value") is current
    assert registry.bound_names(current) == {"value"}


async def test_kernel_retains_rebound_state(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    producer = exec_req.get("state, set_state = mo.state(0)")
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            producer,
            exec_req.get("result = state()"),
        ]
    )
    registry = get_context().state_registry
    previous_ref = weakref.ref(k.globals["state"])
    assert registry.bound_names(k.globals["state"]) == {"state"}

    await k.run(
        [
            exec_req.get_with_id(
                producer.cell_id, "state, set_state = mo.state(1)"
            )
        ]
    )
    gc.collect()

    assert previous_ref() is None
    assert registry.lookup("state") is k.globals["state"]
    assert registry.bound_names(k.globals["state"]) == {"state"}
    assert k.globals["result"] == 1
