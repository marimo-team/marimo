# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def legacy_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.copytree(
        Path(__file__).parent / "cache-dumps",
        tmp_path / "tests/_save/cache-dumps",
    )
    monkeypatch.chdir(tmp_path)


@pytest.mark.usefixtures("legacy_cache_dir")
class TestVersionCache:
    @staticmethod
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_v4_pickle_recomputes(app) -> None:
        @app.cell
        def _():
            unhashable = [object()]

        @app.cell
        def v1(unhashable) -> tuple[int]:
            # Check top level import
            from marimo import persistent_cache

            ref = 1
            with persistent_cache(
                name="pickle-dump-v4",
                save_path="tests/_save/cache-dumps",
                method="pickle",
            ) as cache:
                value = 1 + len(unhashable) + ref
            assert not cache.hit
            assert value == 3

    @staticmethod
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_v4_json_recomputes(app) -> None:
        @app.cell
        def _():
            unhashable = [object()]

        @app.cell
        def v1(unhashable) -> tuple[int]:
            # Check top level import
            from marimo import persistent_cache

            ref = 1
            with persistent_cache(
                name="json-dump-v4",
                save_path="tests/_save/cache-dumps",
                method="json",
            ) as cache:
                value = 1 + len(unhashable) + ref
            assert not cache.hit
            assert value == 3
