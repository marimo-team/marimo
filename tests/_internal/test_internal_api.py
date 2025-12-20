from __future__ import annotations

from tests.mocks import snapshotter
from tests.utils import explore_module

snapshot = snapshotter(__file__)


def test_internal_api():
    import marimo._internal as internal

    results = explore_module(internal)
    assert len(results) > 0
    snapshot("internal_api.txt", "\n".join(results))
