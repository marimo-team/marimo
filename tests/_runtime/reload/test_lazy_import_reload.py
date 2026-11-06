# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import copy
import sys
from queue import Queue
from typing import TYPE_CHECKING, Literal

import pytest
from reload_test_utils import update_file

import marimo._runtime.reload.module_watcher as mw
from marimo._ast.names import SETUP_CELL_NAME
from marimo._config.config import DEFAULT_CONFIG
from marimo._runtime.commands import (
    ExecuteCellCommand,
    ExecuteStaleCellsCommand,
    UpdateUserConfigCommand,
)
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable, Iterator

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 15), reason="`lazy import` requires Python 3.15"
)

INTERVAL = 0.2
SETUP = CellId_t(SETUP_CELL_NAME)


@pytest.fixture
def module_file(
    tmp_path: pathlib.Path,
    py_modname: str,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[pathlib.Path]:
    monkeypatch.setattr(mw, "_TEST_SLEEP_INTERVAL", INTERVAL)
    monkeypatch.syspath_prepend(tmp_path)
    py_file = tmp_path / f"{py_modname}.py"
    py_file.write_text("def foo():\n    return 1\n")
    yield py_file
    sys.modules.pop(py_modname, None)


async def _wait_for(predicate: Callable[[], bool], polls: int = 25) -> bool:
    for _ in range(polls):
        await asyncio.sleep(INTERVAL)
        if predicate():
            return True
    return predicate()


def _set_mode(k: Kernel, mode: Literal["lazy", "autorun"]) -> None:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["runtime"]["auto_reload"] = mode
    k.set_user_config(UpdateUserConfigCommand(config=config))


@pytest.mark.parametrize(
    ("setup_code", "reader"),
    [
        ("import {m}", "x = {m}.foo()"),
        ("lazy import {m}", "x = {m}.foo()"),
        ("from {m} import foo", "x = foo()"),
        ("lazy from {m} import foo", "x = foo()"),
    ],
    ids=["import", "lazy-import", "from-import", "lazy-from-import"],
)
async def test_setup_import_reloads_in_lazy_mode(
    module_file: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
    setup_code: str,
    reader: str,
) -> None:
    k = execution_kernel
    _set_mode(k, "lazy")
    await k.run(
        [
            ExecuteCellCommand(
                cell_id=SETUP, code=setup_code.format(m=py_modname)
            ),
            er := exec_req.get(reader.format(m=py_modname)),
        ]
    )
    assert not k.errors, k.errors
    assert k.globals["x"] == 1
    setup_cell = k.graph.cells[SETUP]
    assert setup_cell.import_workspace.is_import_block
    update_file(module_file, "def foo():\n    return 2\n")
    assert await _wait_for(lambda: setup_cell.stale)

    await k.run_stale_cells()
    assert k.globals["x"] == 2
    assert not setup_cell.stale
    assert not k.graph.cells[er.cell_id].stale
    assert setup_cell.import_workspace.imported_defs == setup_cell.defs


@pytest.mark.parametrize(
    ("setup_code", "reader"),
    [
        ("import {m}", "x = {m}.foo()"),
        ("lazy import {m}", "x = {m}.foo()"),
        ("lazy from {m} import foo", "x = foo()"),
    ],
    ids=["import", "lazy-import", "lazy-from-import"],
)
async def test_setup_import_reloads_in_autorun_mode(
    module_file: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
    setup_code: str,
    reader: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    k = execution_kernel
    queue: Queue[ExecuteStaleCellsCommand] = Queue()
    monkeypatch.setattr(k, "enqueue_control_request", queue.put)
    _set_mode(k, "autorun")
    await k.run(
        [
            ExecuteCellCommand(
                cell_id=SETUP, code=setup_code.format(m=py_modname)
            ),
            exec_req.get(reader.format(m=py_modname)),
        ]
    )
    assert not k.errors, k.errors
    assert k.globals["x"] == 1

    update_file(module_file, "def foo():\n    return 2\n")
    assert await _wait_for(lambda: not queue.empty(), polls=50)
    assert k.graph.cells[SETUP].stale
    request = queue.get_nowait()
    assert request == ExecuteStaleCellsCommand()
    await k.handle_message(request)
    assert k.globals["x"] == 2
    assert not k.graph.get_stale()


async def test_unused_lazy_import_is_not_watched(
    module_file: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
) -> None:
    k = execution_kernel
    _set_mode(k, "lazy")
    await k.run(
        [ExecuteCellCommand(cell_id=SETUP, code=f"lazy import {py_modname}")]
    )
    assert not k.errors
    assert py_modname not in sys.modules

    update_file(module_file, "def foo():\n    return 2\n")
    assert not await _wait_for(lambda: k.graph.cells[SETUP].stale, polls=8)

    await k.run([exec_req.get(f"x = {py_modname}.foo()")])
    assert not k.errors
    assert k.globals["x"] == 2
    assert py_modname in sys.modules
    assert not k.graph.cells[SETUP].stale


@pytest.mark.usefixtures("module_file")
async def test_lazy_import_added_to_setup_does_not_rerun_readers(
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
) -> None:
    k = execution_kernel
    _set_mode(k, "lazy")
    await k.run(
        [
            ExecuteCellCommand(
                cell_id=SETUP, code=f"lazy import {py_modname}"
            ),
            exec_req.get(f"x = ({py_modname}.foo(), object())"),
        ]
    )
    assert not k.errors
    before = k.globals["x"]
    assert before[0] == 1
    await k.run(
        [
            ExecuteCellCommand(
                cell_id=SETUP,
                code=f"lazy import {py_modname}\nlazy import json",
            )
        ]
    )
    assert not k.errors
    assert k.globals["x"] is before
    assert not k.graph.get_stale()
