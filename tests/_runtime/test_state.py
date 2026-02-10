# Copyright 2026 Marimo. All rights reserved.
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_set_and_get_state(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("x = state()"),
            exec_req.get(
                """
                x
                if x == 0:
                    set_state(1)
                """
            ),
        ]
    )

    assert k.globals["x"] == 1


async def test_set_and_get_iteration(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("x = state()"),
            exec_req.get(
                """
                x
                if x < 5:
                    set_state(x + 1)
                """
            ),
        ]
    )

    assert k.globals["x"] == 5


async def test_no_self_loops(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("x = state(); set_state(1)"),
        ]
    )

    assert k.globals["x"] == 0


async def test_allow_self_loops(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                "state, set_state = mo.state(0, allow_self_loops=True)"
            ),
            exec_req.get(
                """
                x = state()
                if x < 3:
                    set_state(x + 1)
                """
            ),
        ]
    )

    assert k.globals["x"] == 3


async def test_update_with_function(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("set_state(lambda v: v + 1)"),
            exec_req.get("x = state()"),
        ]
    )

    assert k.globals["x"] == 1


async def test_set_to_callable_object(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get(
                """
                class F:
                    called = False
                    def __call__(self):
                        self.called = True
                f = F()
                """
            ),
            exec_req.get("set_state(f)"),
            exec_req.get("x = state()"),
        ]
    )

    # state should be an `F` instance that hasn't been called
    assert not k.globals["x"].called


async def test_non_stale_not_run(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("import weakref"),
            exec_req.get(
                """
                class ns:
                    ...
                private = ns()
                private.counter = 0
                ref = weakref.ref(private)
                """
            ),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("set_state(1); x = 0"),
            # this cell runs as a result of the dag; the setter above
            # shouldn't cause it to re-run, even though it calls the getter
            exec_req.get("x; ref().counter += state()"),
        ]
    )

    assert k.globals["private"].counter == 1


async def test_cancelled_not_run(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("set_state(1); x = 0; raise ValueError"),
            # this cell shouldn't run because it was cancelled by
            # its ancestor raising an error
            exec_req.get("x; y = state()"),
        ]
    )

    assert "y" not in k.globals


async def test_set_state_with_overridden_eq(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    create_class = """
    class A:
        def __eq__(self, other):
            # shouldn't be triggered by marimo
            import sys
            sys.exit()
    a = A()
    """
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(create_class),
            exec_req.get("state, set_state = mo.state(None)"),
            exec_req.get("x = state()"),
            exec_req.get(
                """
                x
                if x is None:
                    set_state(a)
                """
            ),
        ]
    )

    assert type(k.globals["x"]).__name__ == "A"


async def test_set_state_not_strict_copied(
    strict_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = strict_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(None)"),
            exec_req.get("a, b = state, set_state"),
        ]
    )

    assert id(k.globals["a"]) == id(k.globals["state"])
    assert id(k.globals["b"]) == id(k.globals["set_state"])


async def test_external_state_update(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """State setter called outside cell execution (no execution context).

    Simulates the pattern where a widget callback or async task calls
    set_state. The __external__ sentinel should skip self-loop prevention
    and downstream cells should re-run.
    """
    k = execution_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("x = state()"),
        ]
    )
    assert k.globals["x"] == 0

    # Call set_state outside any cell execution context,
    # like a widget callback or async task would.
    k.globals["set_state"](42)

    # _find_cells_for_state with __external__ should find the
    # cell that reads state but not loop back to any "setter" cell.
    from marimo._runtime.state import State
    from marimo._types.ids import CellId_t

    state_obj = k.globals["state"]
    assert isinstance(state_obj, State)

    affected = k._find_cells_for_state(state_obj, CellId_t("__external__"))
    # Should include the cell that reads `state` (x = state())
    assert len(affected) > 0

    # The cell that defines state should NOT be in affected
    # (it defines but doesn't read it as a ref)
    define_cell_id = list(k.graph.cells.keys())[1]  # "state, set_state = ..."
    assert define_cell_id not in affected


async def test_external_set_state_reruns_dependent_cell(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Calling set_state from outside a cell (async task / widget callback)
    should re-run downstream cells that read the state."""
    k = execution_kernel

    # Wire enqueue so run_stale_cells can actually flush the update
    k.enqueue_control_request = lambda _: None  # type: ignore

    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("result = state()"),
        ]
    )
    assert k.globals["result"] == 0

    # Simulate a widget callback / async task calling set_state
    k.globals["set_state"](42)

    # Flush — in production the event loop processes this automatically
    await k.run_stale_cells()

    assert k.globals["result"] == 42
