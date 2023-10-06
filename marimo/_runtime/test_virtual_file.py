# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.conftest import ExecReqProvider
from marimo._runtime.context import get_context
from marimo._runtime.requests import DeleteRequest
from marimo._runtime.runtime import Kernel


def test_virtual_file_creation(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                bytestream = io.BytesIO(b"hello world")
                pdf_plugin = mo.pdf(bytestream)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname, _ in get_context().virtual_file_registry.registry.items():
        assert fname.endswith(".pdf")


def test_virtual_file_deletion(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            er := exec_req.get(
                """
                import io
                import marimo as mo
                bytestream = io.BytesIO(b"hello world")
                pdf_plugin = mo.pdf(bytestream)
                """
            ),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    for fname, _ in get_context().virtual_file_registry.registry.items():
        assert fname.endswith(".pdf")

    k.delete(DeleteRequest(er.cell_id))
    assert not get_context().virtual_file_registry.registry
