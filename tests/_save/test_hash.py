# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

import pytest

from marimo._ast.app import App


class TestHash:
    @staticmethod
    def test_content_hash() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = 8
            assert cache._cache.cache_type == "ContentAddressed"
            return Y

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
        def load() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            expected_hash = "vi8ruEJL5Wja4sNnDwJZV8b0FGEOHOn_LOJY8RG51W4"

            return expected_hash, persistent_cache, MockLoader

        @app.cell
        def one(expected_hash, persistent_cache, MockLoader) -> tuple[int]:
            _a = 1
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                _X = 10 + _a
            assert _X == 7
            print(_cache._cache.hash)
            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash
            return

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
            print(_cache._cache.hash)
            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash
            # and a post block difference
            Z = 11
            return Z

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
            return Y

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
                _X = (
                    10
                    + _a[0]  # Comment
                    - len(shared)
                )
            assert _X == 7
            print(_cache._cache.hash)
            assert (
                _cache._cache.hash
                == "84XqUk17Yiuz_jlAVbtdCOvWHrUFj-YApa7-0rB8Kl8"
            )
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
            print(_cache._cache.hash)
            assert (
                _cache._cache.hash
                == "84XqUk17Yiuz_jlAVbtdCOvWHrUFj-YApa7-0rB8Kl8"
            )
            assert _cache._cache.cache_type == "ContextExecutionPath"
            # and a post block difference
            Z = 11
            return Z

        app.run()
