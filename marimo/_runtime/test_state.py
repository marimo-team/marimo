# Copyright 2023 Marimo. All rights reserved.
from marimo._runtime.conftest import ExecReqProvider
from marimo._runtime.runtime import Kernel


def test_set_and_state(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
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


def test_set_and_get_iteration(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
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


def test_no_self_loops(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("x = state(); set_state(1)"),
        ]
    )

    assert k.globals["x"] == 0


def test_update_with_function(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("set_state(lambda v: v + 1)"),
            exec_req.get("x = state()"),
        ]
    )

    assert k.globals["x"] == 1


def test_set_to_callable_object(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
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


def test_non_stale_not_run(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                class ns:
                    ...
                private = ns()
                private.counter = 0
                """
            ),
            exec_req.get("state, set_state = mo.state(0)"),
            exec_req.get("set_state(1); x = 0"),
            # this cell runs as a result of the dag; the setter above
            # shouldn't cause it to re-run, even though it calls the getter
            exec_req.get("x; private.counter += state()"),
        ]
    )

    assert k.globals["private"].counter == 1


def test_cancelled_not_run(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
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


def test_set_state_with_overriden_eq(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    create_class = """
    class A:
        def __eq__(self, other):
            # shouldn't be triggered by marimo
            import sys
            sys.exit()
    a = A()
    """
    k.run(
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
