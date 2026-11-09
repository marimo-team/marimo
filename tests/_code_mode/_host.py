# Copyright 2026 Marimo. All rights reserved.
"""Host document transport for API tests; cell execution stays in the kernel."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch
from weakref import WeakKeyDictionary

from marimo._code_mode._context import AsyncCodeModeContext
from marimo._core import protocol
from marimo._core.document import Document
from marimo._core.errors import Conflict, HostError
from marimo._core.executions import Executions
from marimo._core.notebook import Notebook
from marimo._core.operations import problem_for
from marimo._core.stream import Stream
from marimo._messaging.host import DocumentRequest, DocumentSnapshot
from marimo._messaging.notebook.document import (
    NotebookDocument,
    notebook_document_context,
)
from marimo._runtime.commands import DocumentReplyCommand, EditCellsCommand
from marimo._server.host.document import apply_to_document, sources

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._runtime.runtime import Kernel


documents: WeakKeyDictionary[Kernel, NotebookDocument] = WeakKeyDictionary()
updates: WeakKeyDictionary[Kernel, list[EditCellsCommand]] = (
    WeakKeyDictionary()
)


@contextmanager
def host_context(
    kernel: Kernel,
    document: NotebookDocument,
    *,
    skip_staleness_check: bool = False,
) -> Iterator[AsyncCodeModeContext]:
    document = documents.setdefault(kernel, document)
    queued = updates.setdefault(kernel, [])
    notebook = Notebook(
        protocol.NotebookId("test"),
        Document(sources(document.cells), {}),
        Executions(),
        Mock(),
        Stream(),
    )

    async def request(message: DocumentRequest) -> DocumentReplyCommand:
        notebook.replace(sources(document.cells), {})
        try:
            inline_id = None
            if message.changes is not None:
                notebook.edit(message.changes, request_id=message.request_id)
                _, command = apply_to_document(document, notebook.document)
                if command is not None:
                    inline_id = command.edit_id = message.request_id
                    queued.append(command)
            for target in message.cells:
                cell = notebook.document.cell(target.id)
                if cell is None or cell.etag != target.etag:
                    raise Conflict("Cell changed before the inline run")
            return DocumentReplyCommand(
                request_id=message.request_id,
                inline_id=inline_id,
                document=DocumentSnapshot(
                    cells=tuple(notebook.document), app_config={}
                ),
            )
        except HostError as exc:
            return DocumentReplyCommand(
                request_id=message.request_id, problem=problem_for(exc)
            )

    with (
        notebook_document_context(deepcopy(document)),
        patch.object(kernel.document_requests, "request", request),
    ):
        yield AsyncCodeModeContext(
            kernel, skip_staleness_check=skip_staleness_check
        )
