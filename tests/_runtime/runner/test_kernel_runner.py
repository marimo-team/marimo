from typing import cast

import pytest

from marimo._runtime.app.kernel_runner import AppKernelRunner
from marimo._types.ids import CellId_t


def _make_runner():
    # Bypass __init__ since we only test caching logic
    runner = AppKernelRunner.__new__(AppKernelRunner)
    runner._previously_seen_defs = None
    runner._outputs = {cast(CellId_t, "cell-1"): "dummy"}
    return runner


@pytest.mark.requires("numpy")
def test_numpy_defs_do_not_crash_and_invalidate_cache():
    runner = _make_runner()

    import numpy as np

    defs1 = {"arr": np.ones(1)}
    defs2 = {"arr": np.zeros(2)}

    runner._previously_seen_defs = defs1

    # Must not raise ValueError
    cached = runner.are_outputs_cached(defs2)

    assert cached is False


@pytest.mark.requires("numpy")
def test_numpy_defs_equal_use_cache():
    runner = _make_runner()

    import numpy as np

    arr = np.array([1, 2, 3])
    defs1 = {"arr": arr}
    defs2 = {"arr": arr.copy()}  # different object, same values

    runner._previously_seen_defs = defs1

    cached = runner.are_outputs_cached(defs2)

    assert cached is True
