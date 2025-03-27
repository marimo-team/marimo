# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pytest


class TestVersionCache:
    @staticmethod
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_load_v1_pickle(app) -> None:
        @app.cell
        def _():
            unhashable = [object()]

        @app.cell
        def v1(unhashable) -> tuple[int]:
            # Check top level import
            from marimo import persistent_cache

            ref = 1
            with persistent_cache(
                name="pickle-dump-v1", save_path="tests/_save/cache-dumps"
            ) as cache:
                value = 1 + len(unhashable) + ref
            assert cache.hit
            assert value == 3

    @staticmethod
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_load_v1_json(app) -> None:
        @app.cell
        def _():
            unhashable = [object()]

        @app.cell
        def v1(unhashable) -> tuple[int]:
            # Check top level import
            from marimo import persistent_cache

            ref = 1
            with persistent_cache(
                name="json-dump-v1",
                save_path="tests/_save/cache-dumps",
                method="json",
            ) as cache:
                value = 1 + len(unhashable) + ref
            assert cache.hit
            assert value == 3
