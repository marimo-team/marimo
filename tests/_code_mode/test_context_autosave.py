# Copyright 2026 Marimo. All rights reserved.
"""End-to-end tests: code_mode mutations → interceptor → file on disk.

These tests connect two well-tested pieces (``code_mode`` producing
transactions and ``NotificationListenerExtension`` consuming them) by
taking the transactions code_mode emits from a real ``Kernel`` and
feeding them through the auto-save interceptor against a real
``AppFileManager`` backed by a temp file.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from marimo._ast.cell_id import CellIdGenerator
from marimo._code_mode._context import AsyncCodeModeContext
from marimo._messaging.notebook.document import (
    NotebookCell,
    NotebookDocument,
    notebook_document_context,
)
from marimo._messaging.notification import (
    NotebookDocumentTransactionNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._session.extensions.extensions import (
    NotificationListenerExtension,
)
from marimo._session.model import SessionMode
from marimo._session.notebook import AppFileManager

if TYPE_CHECKING:
    from collections.abc import Generator

    from marimo._runtime.runtime import Kernel


INITIAL_NOTEBOOK_PY = """
import marimo
__generated_with = "0.0.1"
app = marimo.App()

@app.cell
def _():
    return

if __name__ == "__main__":
    app.run()
"""

INITIAL_NOTEBOOK_MD = """---
title: Test
marimo-version: "0.0.1"
---

```python {.marimo}
```
"""


@contextmanager
def _ctx(k: Kernel) -> Generator[AsyncCodeModeContext, None, None]:
    cells = [
        NotebookCell(id=cid, code=cell.code, name="", config=cell.config)
        for cid, cell in k.graph.cells.items()
    ]
    doc = NotebookDocument(cells)
    with notebook_document_context(doc):
        ctx = AsyncCodeModeContext(k)
        ctx._id_generator = CellIdGenerator(seed=7)
        ctx._id_generator.seen_ids = set(doc.cell_ids)
        yield ctx


def _read_disk(app_file_manager: AppFileManager) -> str:
    """Sync helper to read a notebook file from disk (avoids ASYNC240 in
    async tests driven by ``pytest-asyncio`` + code_mode fixtures)."""
    path = app_file_manager.path
    assert path is not None
    return Path(path).read_text()


def _make_notebook_fixture(filename: str, contents: str):
    """Build a parametrizable fixture that creates an AppFileManager backed
    by ``tmp_path / filename`` pre-populated with ``contents``."""

    @pytest.fixture
    def _fixture(tmp_path: Path) -> AppFileManager:
        temp_file = tmp_path / filename
        temp_file.write_text(contents)
        return AppFileManager(filename=str(temp_file))

    return _fixture


py_notebook = _make_notebook_fixture("notebook.py", INITIAL_NOTEBOOK_PY)
md_notebook = _make_notebook_fixture("notebook.md", INITIAL_NOTEBOOK_MD)


@pytest.fixture
def ext() -> NotificationListenerExtension:
    kernel_manager = Mock()
    kernel_manager.mode = SessionMode.EDIT
    queue_manager = Mock()
    queue_manager.stream_queue = None
    return NotificationListenerExtension(kernel_manager, queue_manager)


def _make_session_for(app_file_manager: AppFileManager) -> Mock:
    s = Mock()
    s.app_file_manager = app_file_manager
    s.document = NotebookDocument()
    s.notify = Mock()
    return s


async def _drain(
    k: Kernel,
    ext: NotificationListenerExtension,
    session: Mock,
) -> None:
    """Forward every NotebookDocumentTransactionNotification on ``k.stream``
    through the interceptor so disk state catches up with the kernel graph.

    Auto-save is dispatched to the default executor when a running loop is
    detected, so after feeding messages we must await the pending futures
    before asserting on the file contents.
    """
    for notif in list(k.stream.operations):
        if isinstance(notif, NotebookDocumentTransactionNotification):
            ext._on_kernel_message(session, serialize_kernel_message(notif))
    if ext._pending_autosaves:
        await asyncio.gather(*ext._pending_autosaves)
        ext._pending_autosaves.clear()


class TestCodeModeAutoSavePy:
    """code_mode ops land on a ``.py`` file on disk."""

    async def test_create_cell_persists(
        self,
        k: Kernel,
        py_notebook: AppFileManager,
        ext: NotificationListenerExtension,
    ) -> None:
        session = _make_session_for(py_notebook)
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.create_cell("greeting = 42")
        await _drain(k, ext, session)

        contents = _read_disk(py_notebook)
        assert "greeting = 42" in contents
        # Must be serialized as a proper @app.cell, not an unparsable fallback
        assert "_unparsable_cell" not in contents

    async def test_edit_cell_persists(
        self,
        k: Kernel,
        py_notebook: AppFileManager,
        ext: NotificationListenerExtension,
    ) -> None:
        session = _make_session_for(py_notebook)
        with _ctx(k) as ctx:
            async with ctx as nb:
                cid = nb.create_cell("x = 1")
            async with ctx as nb:
                nb.edit_cell(cid, code="x = 999")
        await _drain(k, ext, session)

        contents = _read_disk(py_notebook)
        assert "x = 999" in contents
        assert "x = 1\n" not in contents

    async def test_delete_cell_persists(
        self,
        k: Kernel,
        py_notebook: AppFileManager,
        ext: NotificationListenerExtension,
    ) -> None:
        session = _make_session_for(py_notebook)
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.create_cell("keep = 1")
                drop = nb.create_cell("drop = 2")
            async with ctx as nb:
                nb.delete_cell(drop)
        await _drain(k, ext, session)

        contents = _read_disk(py_notebook)
        assert "keep = 1" in contents
        assert "drop = 2" not in contents

    async def test_mixed_batch_persists(
        self,
        k: Kernel,
        py_notebook: AppFileManager,
        ext: NotificationListenerExtension,
    ) -> None:
        """Create + edit + delete in a single context block all land."""
        session = _make_session_for(py_notebook)
        with _ctx(k) as ctx:
            async with ctx as nb:
                first = nb.create_cell("first = 1")
                second = nb.create_cell("second = 2")
            async with ctx as nb:
                nb.edit_cell(first, code="first = 100")
                nb.create_cell("third = 3")
                nb.delete_cell(second)
        await _drain(k, ext, session)

        contents = _read_disk(py_notebook)
        assert "first = 100" in contents
        assert "third = 3" in contents
        assert "second = 2" not in contents


class TestCodeModeAutoSaveMd:
    """code_mode ops land on a ``.md`` file on disk."""

    async def test_create_cell_persists(
        self,
        k: Kernel,
        md_notebook: AppFileManager,
        ext: NotificationListenerExtension,
    ) -> None:
        session = _make_session_for(md_notebook)
        with _ctx(k) as ctx:
            async with ctx as nb:
                nb.create_cell("answer = 42")
        await _drain(k, ext, session)

        assert "answer = 42" in _read_disk(md_notebook)


class TestExecutorOrdering:
    """A slower earlier save must never overwrite a newer one."""

    async def test_rapid_mutations_preserve_latest_state(
        self,
        k: Kernel,
        py_notebook: AppFileManager,
        ext: NotificationListenerExtension,
    ) -> None:
        """Rapid-fire kernel mutations should all serialize through the
        single-worker executor in FIFO order, leaving the newest snapshot
        on disk."""
        session = _make_session_for(py_notebook)
        with _ctx(k) as ctx:
            async with ctx as nb:
                cid = nb.create_cell("version = 1")
            async with ctx as nb:
                nb.edit_cell(cid, code="version = 2")
            async with ctx as nb:
                nb.edit_cell(cid, code="version = 3")
            async with ctx as nb:
                nb.edit_cell(cid, code="version = 4")

        await _drain(k, ext, session)

        contents = _read_disk(py_notebook)
        assert "version = 4" in contents
        # None of the earlier snapshots should have clobbered the latest
        assert "version = 1\n" not in contents
        assert "version = 2\n" not in contents
        assert "version = 3\n" not in contents
