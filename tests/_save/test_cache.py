# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

import textwrap

from marimo._ast.app import App
from marimo._runtime.requests import ExecutionRequest
from marimo._runtime.runtime import Kernel


class TestScriptCache:
    @staticmethod
    def test_cache_miss() -> None:
        app = App()
        app._anonymous_file = True

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
        app._anonymous_file = True

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

    @staticmethod
    def test_cache_hit_whitespace() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            # fmt: off
            with persistent_cache(name="one", _loader=MockLoader(data={"X": 7, "Y": 8})) as cache: # noqa: E501
                Y = 9
                X = 10
            # fmt: on
            assert X == 7
            assert cache._cache.defs == {"X": 7, "Y": 8}
            assert not cache._loader._saved
            assert cache._loader._loaded
            return X, Y, persistent_cache

        app.run()


class TestAppCache:
    async def test_cache_miss(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent("""
                from marimo._save.save import persistent_cache
                from tests._save.mocks import MockLoader

                with persistent_cache(name="one") as cache:
                    Y = 9
                    X = 10
                Z = 3
                """),
                ),
            ]
        )
        assert k.globals["Y"] == 9
        assert k.globals["X"] == 10
        assert k.globals["Z"] == 3

    async def test_cache_hit(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent("""
                from marimo._save.save import persistent_cache
                from tests._save.mocks import MockLoader

                with persistent_cache(
                    name="one", _loader=MockLoader(data={"X": 7, "Y": 8})
                ) as cache:
                    Y = 9
                    X = 10
                Z = 3
                """),
                ),
            ]
        )
        assert k.globals["X"] == 7
        assert k.globals["Y"] == 8
        assert k.globals["Z"] == 3

    async def test_cache_one_line(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent("""
        from marimo._save.save import persistent_cache
        from tests._save.mocks import MockLoader

        with persistent_cache(name="one", _loader=MockLoader(data={"X": 1})):
            X = 1
        Y = 2
                """),
                ),
            ]
        )
        assert k.errors == {}
        assert k.errors == {}
        assert k.globals["X"] == 1
        assert k.globals["Y"] == 2

    async def test_cache_comment_line(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent("""
                from marimo._save.save import persistent_cache
                from tests._save.mocks import MockLoader

                with persistent_cache(name="one"):
                    # Comment

                    # whitespace
                    X = 1 # Comment
                    Y = 2
                """),
                ),
            ]
        )
        assert k.errors == {}
        assert k.errors == {}
        assert k.globals["X"] == 1
        assert k.globals["Y"] == 2
