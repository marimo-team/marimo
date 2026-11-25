# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import cProfile
from contextlib import contextmanager
from inspect import unwrap
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping


@contextmanager
def assert_call_budget(
    budgets: Mapping[Callable[..., Any], int],
) -> Iterator[None]:
    """Bound calls to Python functions during a synchronous or async operation.

    Count work instead of elapsed time so checks tolerate loaded CI machines.
    Pass the original function (or bound method), not a mock. Decorated
    functions are unwrapped to count their bodies. Use separate budgets for
    setup, per-run, and per-cell work; parameterize notebook sizes to catch
    scans accidentally moved inside cell loops.
    """
    functions = {
        unwrap(function): limit for function, limit in budgets.items()
    }
    profiler = cProfile.Profile()
    with profiler:
        yield
    counts = {entry.code: entry.callcount for entry in profiler.getstats()}
    for function, limit in functions.items():
        count = counts.get(function.__code__, 0)
        assert count <= limit, (
            f"{function.__qualname__}: {count} calls exceeds budget of {limit}"
        )
