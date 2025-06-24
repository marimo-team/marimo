# Copyright 2024 Marimo. All rights reserved.
from marimo._runtime.runtime import Kernel
from marimo._runtime.state import State, StateRegistry
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


def test_retain_active_states() -> None:
    state_registry = StateRegistry()
    state = State(None)
    state_registry.register(state, "state")

    assert state_registry.lookup("state")
    assert state_registry.bound_names(state) == {"state"}

    state_registry.retain_active_states({"state"})

    assert state_registry.lookup("state")
    assert state_registry.bound_names(state) == {"state"}
