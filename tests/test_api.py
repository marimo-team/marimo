from __future__ import annotations

from tests.mocks import snapshotter
from tests.utils import explore_module

snapshot = snapshotter(__file__)


def test_api():
    import marimo as mo

    results = explore_module(mo)
    assert len(results) > 0
    snapshot("api.txt", "\n".join(results))
