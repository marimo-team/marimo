# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.conftest import ExecReqProvider
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel


# TODO: colocate test with UIElementRegistry file; requires refactoring
# pytest's conftests ...
def test_cached_element_still_registered(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    k.run(
        [
            exec_req.get("import functools"),
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                @functools.lru_cache
                def slider():
                    return mo.ui.slider(1, 10)
                """
            ),
            (construct_slider := exec_req.get("s = slider()")),
        ]
    )
    # Make sure that the slider is registered
    s = k.globals["s"]
    assert get_context().ui_element_registry.get_object(s._id) == s

    # Re-run the cell but fetch the same slider, since we're using
    # functools.cache. Make sure it's still registered!
    k.run([construct_slider])
    assert get_context().ui_element_registry.get_object(s._id) == s
