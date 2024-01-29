# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.context import get_context
from marimo._runtime.requests import DeleteRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


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

    k.delete(DeleteRequest(cell_id=er.cell_id))
    assert not get_context().virtual_file_registry.registry


def test_cached_virtual_file_not_deleted(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                import functools
                """
            ),
            vfile_cache := exec_req.get(
                """
                @functools.lru_cache()
                def create_vfile(arg):
                    del arg
                    bytestream = io.BytesIO(b"hello world")
                    return mo.pdf(bytestream)
                """
            ),
            create_vfile_1 := exec_req.get("create_vfile(1)"),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1

    # Rerun the cell that created the vfile: make sure that the vfile
    # still exists
    k.run([create_vfile_1])
    assert len(get_context().virtual_file_registry.registry) == 1

    # Create a new vfile, make sure we have two now
    k.run([create_vfile_2 := exec_req.get("create_vfile(2)")])
    assert len(get_context().virtual_file_registry.registry) == 2

    # Remove the cells that create the vfiles
    k.delete(DeleteRequest(cell_id=create_vfile_1.cell_id))
    k.delete(DeleteRequest(cell_id=create_vfile_2.cell_id))

    # Reset the vfile cache
    k.run([vfile_cache])


def test_cell_deletion_clears_vfiles(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                import functools
                """
            ),
            vfile_cache := exec_req.get(
                """
                @functools.lru_cache()
                def create_vfile(arg):
                    del arg
                    bytestream = io.BytesIO(b"hello world")
                    return mo.pdf(bytestream)
                """
            ),
            exec_req.get("create_vfile(1)"),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1

    # Delete the vfile cache: virtual file registry should be empty
    k.delete(DeleteRequest(cell_id=vfile_cache.cell_id))
    assert len(get_context().virtual_file_registry.registry) == 0


def test_vfile_refcount_incremented(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                import functools
                """
            ),
            exec_req.get(
                """
                @functools.lru_cache()
                def create_vfile(arg):
                    del arg
                    bytestream = io.BytesIO(b"hello world")
                    return mo.pdf(bytestream)
                """
            ),
            exec_req.get("md = mo.md(f'{create_vfile(1)}')"),
        ]
    )
    assert len(get_context().virtual_file_registry.registry) == 1
    vfile = list(get_context().virtual_file_registry.filenames())[0]

    #   1 reference for the cached `mo.pdf`
    # + 1 reference for the markdown
    # ---
    #   2 references
    assert get_context().virtual_file_registry.refcount(vfile) == 2


def test_vfile_refcount_decremented(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                import gc
                """
            ),
            # no caching in this test
            exec_req.get(
                """
                def create_vfile(arg):
                    del arg
                    bytestream = io.BytesIO(b"hello world")
                    return mo.pdf(bytestream)
                """
            ),
            make_vfile := exec_req.get("mo.md(f'{create_vfile(1)}')"),
        ]
    )
    ctx = get_context()
    assert len(ctx.virtual_file_registry.registry) == 1
    vfile = list(ctx.virtual_file_registry.filenames())[0]

    # 0 references because HTML not bound to a variable
    # NB: this test may be flaky! refcount decremented when `__del__` is called
    # but we can't rely on when it will be called.
    k.run([exec_req.get("gc.collect()")])
    assert ctx.virtual_file_registry.refcount(vfile) == 0

    # this should dispose the old vfile (because its refcount is 0) and create
    # a new one
    k.run([make_vfile])
    # the previous vfile should not be in the registry
    assert vfile not in ctx.virtual_file_registry.registry
    assert len(ctx.virtual_file_registry.registry) == 1


def test_cached_vfile_disposal(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            exec_req.get(
                """
                import io
                import marimo as mo
                import functools
                """
            ),
            exec_req.get(
                """
                vfiles = []
                def create_vfile(arg):
                    del arg
                    bytestream = io.BytesIO(b"hello world")
                    return mo.pdf(bytestream)
                """
            ),
            append_vfile := exec_req.get("vfiles.append(create_vfile(1))"),
        ]
    )
    ctx = get_context()
    assert len(ctx.virtual_file_registry.registry) == 1
    vfile = list(ctx.virtual_file_registry.filenames())[0]

    # 1 reference, in the list
    assert ctx.virtual_file_registry.refcount(vfile) == 1

    # clear the list, refcount should be decremented
    k.run([exec_req.get("vfiles[:] = []")])
    # NB: this test may be flaky! refcount decremented when `__del__` is called
    # but we can't rely on when it will be called.
    k.run([exec_req.get("import gc; gc.collect()")])
    assert ctx.virtual_file_registry.refcount(vfile) == 0

    # create another vfile. the old one should be deleted
    k.run([append_vfile])
    assert len(ctx.virtual_file_registry.registry) == 1
    assert vfile not in ctx.virtual_file_registry.filenames()
