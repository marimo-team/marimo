# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

from typing import Any

import pytest

from marimo._ast.app import App
from marimo._dependencies.dependencies import DependencyManager


class TestHash:
    @staticmethod
    def test_pure_hash() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = [1, 2, 3]
                Z = len(Y)
            assert cache._cache.cache_type == "Pure"
            return Y, Z

        app.run()

    @staticmethod
    def test_content_hash() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            a = 1
            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = a
            assert cache._cache.cache_type == "ContentAddressed"
            return (Y,)

        app.run()

    # Note: Hash may change based on byte code, so pin to particular version
    @staticmethod
    @pytest.mark.skipif(
        "sys.version_info < (3, 11) or sys.version_info >= (3, 12)"
    )
    def test_content_reproducibility() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def load() -> tuple[Any]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            expected_hash = "KJzgi4EM10ZHAqR9F81JQQchDN9n_LQpCGGFfdaEYyE"

            return expected_hash, persistent_cache, MockLoader

        @app.cell
        def one(expected_hash, persistent_cache, MockLoader) -> None:
            _a = 1
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                _X = 10 + _a
            assert _X == 7
            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, _cache._cache.hash

        @app.cell
        def two(expected_hash, persistent_cache, MockLoader) -> tuple[int]:
            # The same as cell one, but with this comment
            _a = 2 - 1

            # Some white space
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                # More Comments
                _X = 10 + _a
            assert _X == 7
            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, _cache._cache.hash
            # and a post block difference
            Z = 11
            return (Z,)

        app.run()

    @staticmethod
    def test_execution_hash() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            non_primitive = [object()]

            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = 8 + len(non_primitive)
            assert cache._cache.cache_type == "ContextExecutionPath"
            return (Y,)

        app.run()

    @staticmethod
    @pytest.mark.skipif(
        "sys.version_info < (3, 11) or sys.version_info >= (3, 12)"
    )
    def test_execution_reproducibility() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def load() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            shared = [None, object()]
            return persistent_cache, MockLoader, shared

        @app.cell
        def one(persistent_cache, MockLoader, shared) -> tuple[int]:
            _a = [1]
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                _X = 10 + _a[0] - len(shared)  # Comment
            assert _X == 7
            assert (
                _cache._cache.hash
                == "84XqUk17Yiuz_jlAVbtdCOvWHrUFj-YApa7-0rB8Kl8"
            ), _cache._cache.hash
            assert _cache._cache.cache_type == "ContextExecutionPath"
            return

        @app.cell
        def two(persistent_cache, MockLoader, shared) -> tuple[int]:
            # The same as cell one, but with this comment
            _a = [
                1,  # Comment
            ]

            # Some white space
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                # More Comments
                _X = 10 + _a[0] - len(shared)
            assert _X == 7
            assert (
                _cache._cache.hash
                == "84XqUk17Yiuz_jlAVbtdCOvWHrUFj-YApa7-0rB8Kl8"
            ), _cache._cache.hash
            assert _cache._cache.cache_type == "ContextExecutionPath"
            # and a post block difference
            Z = 11
            return (Z,)

        app.run()

    @staticmethod
    def test_transitive_content_hash() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def load() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            shared = [None, object()]
            return persistent_cache, MockLoader, shared

        @app.cell
        def one(persistent_cache, MockLoader, shared) -> tuple[int]:
            _a = len(shared)
            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = 8 + _a
            assert cache._cache.cache_type == "ContentAddressed"
            return (Y,)

        app.run()

    @staticmethod
    def test_function_ui_content_hash() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def load() -> tuple[Any]:
            import marimo as mo
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            slider = mo.ui.slider(1, 10)

            def shared() -> str:
                return "x" * slider.value

            return persistent_cache, MockLoader, shared, slider

        @app.cell
        def one(persistent_cache, MockLoader, shared, slider) -> tuple[Any]:
            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                _Y = len(shared())
            slider._update(7)
            assert cache._cache.cache_type == "ExecutionPath"
            return (cache,)

        @app.cell
        def two(persistent_cache, MockLoader, shared, cache) -> tuple[Any]:
            with persistent_cache(name="two", _loader=MockLoader()) as cache2:
                _Y = len(shared())
            assert cache2._cache.cache_type == "ExecutionPath"
            assert cache2._cache.hash != cache._cache.hash
            return (cache2,)

        app.run()

    @staticmethod
    def test_function_state_content_hash() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def load() -> tuple[Any]:
            import marimo as mo
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            state, set_state = mo.state(0)

            def shared(state) -> str:
                return "x" * state()

            return persistent_cache, MockLoader, shared, state, set_state

        @app.cell
        def one(
            persistent_cache, MockLoader, shared, state, set_state
        ) -> tuple[Any]:
            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                _Y = len(shared(state))
            set_state(1)
            assert cache._cache.cache_type == "ContentAddressed"
            return (cache,)

        @app.cell
        def two(
            persistent_cache, MockLoader, shared, state, cache
        ) -> tuple[Any]:
            with persistent_cache(name="two", _loader=MockLoader()) as cache2:
                _Y = len(shared(state))
            assert cache2._cache.cache_type == "ContentAddressed"
            assert cache2._cache.hash != cache._cache.hash
            return (cache2,)

        app.run()

    @staticmethod
    def test_transitive_execution_path_when_state_dependent() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def load() -> tuple[Any]:
            import marimo as mo
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            state, set_state = mo.state(0)

            def shared() -> str:
                return "x" * state()

            return persistent_cache, MockLoader, shared, state, set_state

        @app.cell
        def one(persistent_cache, MockLoader, shared, set_state) -> tuple[Any]:
            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                _Y = len(shared())
            set_state(1)
            assert cache._cache.cache_type == "ExecutionPath"
            return (cache,)

        @app.cell
        def two(persistent_cache, MockLoader, shared, cache) -> tuple[Any]:
            with persistent_cache(name="two", _loader=MockLoader()) as cache2:
                _Y = len(shared())
            assert cache2._cache.cache_type == "ExecutionPath"
            assert cache2._cache.hash != cache._cache.hash
            return (cache2,)

        app.run()

    @staticmethod
    def test_version_pinning() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def load() -> tuple[Any]:
            import marimo as mo
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            mo.__version__ = "0.0.0"

            return mo, persistent_cache, MockLoader

        @app.cell
        def one(mo, persistent_cache, MockLoader) -> tuple[Any]:
            with persistent_cache(
                name="one", _loader=MockLoader(), pin_modules=True
            ) as cache:
                _Y = len(mo.__version__)
            mo.__version__ = "0.0.1"
            assert cache._cache.cache_type == "ContentAddressed"
            return (cache,)

        @app.cell
        def two(mo, persistent_cache, MockLoader, cache) -> tuple[Any]:
            with persistent_cache(
                name="two", _loader=MockLoader(), pin_modules=True
            ) as cache2:
                _Y = len(mo.__version__)
            mo.__version__ = "0.0.0"
            assert cache2._cache.cache_type == "ContentAddressed"
            assert cache2._cache.hash != cache._cache.hash
            return (cache2,)

        app.run()


class TestDataHash:
    @staticmethod
    @pytest.mark.skipif(
        not DependencyManager.numpy.has(),
        reason="optional dependencies not installed",
    )
    @pytest.mark.skipif(
        "sys.version_info < (3, 11) or sys.version_info >= (3, 12)"
    )
    def test_numpy_hash() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def load() -> tuple[Any]:
            import numpy as np

            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            expected_hash = "iBv13AtI89eagC2BRVcUvIzEWikXVer9RRquL8ARcEU"
            return MockLoader, persistent_cache, expected_hash, np

        @app.cell
        def one(MockLoader, persistent_cache, expected_hash, np) -> tuple[int]:
            _a = np.ones((16, 16)) * 2
            with persistent_cache(name="one", _loader=MockLoader()) as _cache:
                _A = np.sum(_a)
            one = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert (
                _cache._cache.hash == expected_hash
            ), f"expected_hash != {_cache._cache.hash}"
            return (one,)

        @app.cell
        def two(MockLoader, persistent_cache, expected_hash, np) -> tuple[int]:
            _a = np.ones((16, 16)) + np.ones((16, 16))

            with persistent_cache(name="two", _loader=MockLoader()) as _cache:
                _A = np.sum(_a)
            two = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert (
                _cache._cache.hash == expected_hash
            ), f"expected_hash != {_cache._cache.hash}"
            return (two,)

        @app.cell
        def three(one, two) -> None:
            assert one == two
            assert one == 512

        app.run()
