# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

from marimo._ast.app import App


class TestScriptCache:
    @staticmethod
    def test_cache_miss() -> None:
        app = App()

        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = 8
                X = 7
            assert X == 7
            assert cache._cache.defs == {"X": 7, "Y": 8}
            assert cache._loader._saved
            assert not cache._loader._loaded
            return X, Y, persistent_cache

        app.run()

    @staticmethod
    def test_cache_hit() -> None:
        app = App()

        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            with persistent_cache(
                name="one", _loader=MockLoader(data={"X": 7, "Y": 8})
            ) as cache:
                Y = 9
                X = 10
            assert X == 7
            assert cache._cache.defs == {"X": 7, "Y": 8}
            assert not cache._loader._saved
            assert cache._loader._loaded
            return X, Y, persistent_cache

        app.run()
