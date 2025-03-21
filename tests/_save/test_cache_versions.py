# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

import sys
import textwrap
import warnings

import pytest

from marimo._ast.app import App
from marimo._runtime.requests import ExecutionRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


class TestVersionCache:
    @staticmethod
    def test_load_v1_pickle(app) -> None:
        @app.cell
        def _():
            unhashable = [object()]

        @app.cell
        def v1() -> tuple[int]:
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
    def test_load_v1_json(app) -> None:
        @app.cell
        def _():
            unhashable = [object()]

        @app.cell
        def v1() -> tuple[int]:
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
