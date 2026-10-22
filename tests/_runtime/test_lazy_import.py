# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from marimo._ast.names import SETUP_CELL_NAME
from marimo._messaging.errors import LazyImportError
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 15), reason="`lazy import` requires Python 3.15"
)


@pytest.fixture
def lazy_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    module_name = "marimo_lazy_import_test"
    (tmp_path / f"{module_name}.py").write_text("def foo():\n    return 1\n")
    monkeypatch.syspath_prepend(tmp_path)
    yield module_name
    sys.modules.pop(module_name, None)


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

    @pytest.mark.parametrize(
        ("setup_code", "reader"),
        [
            ("lazy import {m}", "{m}.foo()"),
            ("lazy from {m} import foo", "foo()"),
        ],
    )
    async def test_setup_import_is_deferred_until_first_use(
        self,
        execution_kernel: Kernel,
        exec_req: ExecReqProvider,
        lazy_module: str,
        setup_code: str,
        reader: str,
    ) -> None:
        k = execution_kernel
        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t(SETUP_CELL_NAME),
                    code=setup_code.format(m=lazy_module),
                ),
            ]
        )
        assert not k.errors
        assert lazy_module not in sys.modules

        await k.run(
            [
                exec_req.get(
                    f"def use_module():\n    return {reader.format(m=lazy_module)}"
                )
            ]
        )
        assert not k.errors
        assert lazy_module not in sys.modules

        await k.run([exec_req.get("x = use_module()")])
        assert not k.errors
        assert k.globals["x"] == 1
        assert lazy_module in sys.modules
