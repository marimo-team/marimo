# Copyright 2026 Marimo. All rights reserved.
"""Regression tests for the run_button + mo.stop side-effect pattern.

This is the canonical "trigger" pattern for dataflow notebooks — a cell
gated by ``mo.stop(not button.value)`` only fires when the button is
explicitly clicked, never as part of a normal reactive run.

The pattern relies on cross-cell mutation of shared state (the side-effect
cell builds up a list, increments a counter, etc.) which only works in
marimo's relaxed kernel mode (the default for ``marimo edit``); strict
mode re-runs upstream cells on every reactive execution and would reset
that state.
"""

from __future__ import annotations

import pytest

from marimo._runtime.commands import UpdateUIElementCommand
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


@pytest.mark.asyncio
async def test_run_button_gates_side_effect(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """The gated cell stays dormant until the button is clicked."""
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                "send = mo.ui.run_button()\n"
                "customers = ['a@x.com', 'b@x.com']\n"
                "side_effects = []\n"
            ),
            exec_req.get(
                "mo.stop(not send.value)\n"
                "for c in customers:\n"
                "    side_effects.append(c)\n"
            ),
        ]
    )
    assert k.globals["side_effects"] == []

    await k.set_ui_element_value(
        UpdateUIElementCommand.from_ids_and_values(
            [(k.globals["send"]._id, 1)]
        ),
        notify_frontend=False,
    )
    assert k.globals["side_effects"] == ["a@x.com", "b@x.com"]


@pytest.mark.asyncio
async def test_run_button_resets_after_firing(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """After firing, the button's value resets so reactive reruns don't refire."""
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("send = mo.ui.run_button()\ntrigger_count = [0]\n"),
            exec_req.get("mo.stop(not send.value)\ntrigger_count[0] += 1\n"),
        ]
    )
    assert k.globals["trigger_count"][0] == 0

    await k.set_ui_element_value(
        UpdateUIElementCommand.from_ids_and_values(
            [(k.globals["send"]._id, 1)]
        ),
        notify_frontend=False,
    )
    assert k.globals["trigger_count"][0] == 1
    # The kernel-side run_button auto-resets to False, so an unrelated input
    # change doesn't refire the side effect.
    assert k.globals["send"].value is False
