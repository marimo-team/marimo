# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from functools import wraps

import pytest

from tests._runtime._helpers.performance import assert_call_budget


def test_call_budget_counts_decorated_bound_methods() -> None:
    class Work:
        def run(self) -> None:
            pass

    work = Work()

    @wraps(work.run)
    def run() -> None:
        work.run()

    with assert_call_budget({work.run: 1, run: 1}):
        run()

    def run_twice() -> None:
        run()
        run()

    with (
        pytest.raises(AssertionError, match="2 calls exceeds budget of 1"),
        assert_call_budget({run: 1}),
    ):
        run_twice()
