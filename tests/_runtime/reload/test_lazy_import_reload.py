# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import copy
import sys
from queue import Queue
from typing import TYPE_CHECKING

import pytest
from reload_test_utils import update_file

import marimo._runtime.reload.module_watcher as mw
from marimo._ast.names import SETUP_CELL_NAME
from marimo._config.config import DEFAULT_CONFIG
from marimo._runtime.commands import (
    ExecuteCellCommand,
    UpdateUserConfigCommand,
)
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    import pathlib

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 15), reason="`lazy import` requires Python 3.15"
)

INTERVAL = 0.2
SETUP = CellId_t(SETUP_CELL_NAME)


@pytest.fixture(autouse=True)
def _setup_test_sleep():
    old_interval = mw._TEST_SLEEP_INTERVAL
    mw._TEST_SLEEP_INTERVAL = INTERVAL
    yield
    mw._TEST_SLEEP_INTERVAL = old_interval


async def _wait_for(predicate, polls: int = 25) -> bool:
    for _ in range(polls):
        await asyncio.sleep(INTERVAL)
        if predicate():
            return True
    return predicate()


def _module(tmp_path: pathlib.Path, modname: str, value: int) -> pathlib.Path:
    sys.path.append(str(tmp_path))
    py_file = tmp_path / f"{modname}.py"
    py_file.write_text(f"def foo():\n    return {value}\n")
    return py_file


def _set_mode(k: Kernel, mode: str) -> None:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["runtime"]["auto_reload"] = mode
    k.set_user_config(UpdateUserConfigCommand(config=config))


def _stale(k: Kernel) -> set[str]:
    return {str(cid) for cid in k.graph.get_stale()}


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
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
    setup_code: str,
    reader: str,
) -> None:
    k = execution_kernel
    py_file = _module(tmp_path, py_modname, 1)
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
    print(
        "imported_defs after run:", setup_cell.import_workspace.imported_defs
    )

    update_file(py_file, "def foo():\n    return 2\n")
    assert await _wait_for(lambda: setup_cell.stale)
    print("stale after edit:", _stale(k))

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
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
    setup_code: str,
    reader: str,
) -> None:
    k = execution_kernel
    py_file = _module(tmp_path, py_modname, 1)
    # The watcher enqueues a run request; the test harness has no control
    # loop, so run the stale cells by hand as the module watcher tests do.
    queue: Queue[object] = Queue()
    k.enqueue_control_request = lambda req: queue.put(req)
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

    update_file(py_file, "def foo():\n    return 2\n")
    assert await _wait_for(lambda: k.graph.cells[SETUP].stale, polls=50)
    assert not queue.empty()
    await k.run_stale_cells()
    assert k.globals["x"] == 2
    assert not k.graph.get_stale()


async def test_unused_lazy_import_is_not_watched(
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
) -> None:
    """A lazy import that nothing has used yet never loaded the module, so
    an edit on disk is not a reload; the first use reads the new file."""
    k = execution_kernel
    py_file = _module(tmp_path, py_modname, 1)
    _set_mode(k, "lazy")
    await k.run(
        [ExecuteCellCommand(cell_id=SETUP, code=f"lazy import {py_modname}")]
    )
    assert not k.errors
    assert py_modname not in sys.modules

    update_file(py_file, "def foo():\n    return 2\n")
    assert not await _wait_for(lambda: k.graph.cells[SETUP].stale, polls=8)

    await k.run([exec_req.get(f"x = {py_modname}.foo()")])
    assert k.globals["x"] == 2
    assert py_modname in sys.modules
    assert not k.graph.cells[SETUP].stale


async def test_lazy_import_added_to_setup_does_not_rerun_readers(
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
) -> None:
    """Import-only carry-over holds for the setup cell with autoreload on."""
    k = execution_kernel
    _module(tmp_path, py_modname, 1)
    _set_mode(k, "lazy")
    await k.run(
        [
            ExecuteCellCommand(
                cell_id=SETUP, code=f"lazy import {py_modname}"
            ),
            exec_req.get(
                f"import random\nx = ({py_modname}.foo(), random.random())"
            ),
        ]
    )
    before = k.globals["x"]
    await k.run(
        [
            ExecuteCellCommand(
                cell_id=SETUP,
                code=f"lazy import {py_modname}\nlazy import json",
            )
        ]
    )
    assert k.globals["x"] == before
    assert not k.graph.get_stale()
