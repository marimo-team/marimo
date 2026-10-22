# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys

import pytest

from marimo._ast.names import SETUP_CELL_NAME
from marimo._messaging.errors import LazyImportError
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t
from tests.conftest import ExecReqProvider

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 15), reason="`lazy import` requires Python 3.15"
)


class TestLazyImports:
    async def test_lazy_import_in_regular_cell_is_a_syntax_error(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        er = exec_req.get("lazy import numpy")
        await k.run([er])
        assert set(k.errors.keys()) == {er.cell_id}
        error = k.errors[er.cell_id][0]
        assert isinstance(error, LazyImportError)
        assert error.lineno == 1
        assert error.msg == "`lazy import` is only allowed in the setup cell."

    async def test_lazy_import_in_setup_cell_runs(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t(SETUP_CELL_NAME), code="lazy import json"
                ),
                exec_req.get("x = json.dumps(1)"),
            ]
        )
        assert not k.errors
        assert k.globals["x"] == "1"

    async def test_lazy_import_in_setup_cell_runs_in_strict_mode(
        self, strict_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        # Strict execution clones each ref; a lazy proxy must pass through
        # like a module instead of failing to deepcopy.
        k = strict_kernel
        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t(SETUP_CELL_NAME), code="lazy import json"
                ),
                exec_req.get("x = json.dumps(1)"),
            ]
        )
        assert not k.errors
        assert k.globals["x"] == "1"
