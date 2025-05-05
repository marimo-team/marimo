# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

from marimo._ast.app import App


class TestStore:
    def test_store(self, app: App) -> None:
        @app.cell
        def _():
            import marimo as mo
            from tests._save.store.mocks import MockStore

            store = MockStore()
            return store, mo

        @app.cell
        def _(mo, store):
            assert store._cache == {}
            with mo.persistent_cache("mock", store=store) as cache:
                a = 1
                b = 2

            from pathlib import Path

            key = str(Path(f"mock/P_{cache._cache.key.hash}.pickle"))
            assert key in store._cache.keys()
            assert store._cache[key]
