# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from dirty_equals import IsPositiveFloat, IsStr

from marimo._data._external_storage.models import StorageEntry
from marimo._data._external_storage.storage import Obstore
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.notification import (
    StorageDownloadReadyNotification,
    StorageEntriesNotification,
)
from marimo._runtime.commands import (
    ExecuteCellCommand,
    StorageDownloadCommand,
    StorageListEntriesCommand,
)
from marimo._types.ids import CellId_t, RequestId, VariableName
from tests.conftest import MockedKernel

HAS_OBSTORE = DependencyManager.obstore.has()

STORAGE_VAR = "my_store"


class TestExternalStorageErrors:
    """Error-handling tests that don't require a real storage backend."""

    async def test_list_entries_variable_not_found(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        request = StorageListEntriesCommand(
            request_id=RequestId("req-1"),
            namespace="nonexistent_var",
            limit=100,
            prefix=None,
        )
        await k.handle_message(request)

        results = [
            op
            for op in stream.operations
            if isinstance(op, StorageEntriesNotification)
        ]
        assert results == [
            StorageEntriesNotification(
                request_id=RequestId("req-1"),
                entries=[],
                namespace="nonexistent_var",
                prefix=None,
                error="Variable 'nonexistent_var' not found",
            )
        ]

    async def test_list_entries_incompatible_backend(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("0"),
                    code='not_storage = "just a string"',
                ),
            ]
        )

        request = StorageListEntriesCommand(
            request_id=RequestId("req-2"),
            namespace="not_storage",
            limit=100,
            prefix=None,
        )
        await k.handle_message(request)

        results = [
            op
            for op in stream.operations
            if isinstance(op, StorageEntriesNotification)
        ]
        assert results == [
            StorageEntriesNotification(
                request_id=RequestId("req-2"),
                entries=[],
                namespace="not_storage",
                prefix=None,
                error=(
                    "Variable 'not_storage' is not a compatible "
                    "storage backend (expected obstore or fsspec)"
                ),
            )
        ]

    async def test_download_variable_not_found(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        request = StorageDownloadCommand(
            request_id=RequestId("req-3"),
            namespace="nonexistent_var",
            path="data/file.csv",
        )
        await k.handle_message(request)

        results = [
            op
            for op in stream.operations
            if isinstance(op, StorageDownloadReadyNotification)
        ]
        assert results == [
            StorageDownloadReadyNotification(
                request_id=RequestId("req-3"),
                url=None,
                filename=None,
                error="Variable 'nonexistent_var' not found",
            )
        ]

    async def test_download_incompatible_backend(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("0"),
                    code="not_storage = 42",
                ),
            ]
        )

        request = StorageDownloadCommand(
            request_id=RequestId("req-4"),
            namespace="not_storage",
            path="data/file.csv",
        )
        await k.handle_message(request)

        results = [
            op
            for op in stream.operations
            if isinstance(op, StorageDownloadReadyNotification)
        ]
        assert results == [
            StorageDownloadReadyNotification(
                request_id=RequestId("req-4"),
                url=None,
                filename=None,
                error=(
                    "Variable 'not_storage' is not a compatible "
                    "storage backend (expected obstore or fsspec)"
                ),
            )
        ]


@pytest.mark.skipif(not HAS_OBSTORE, reason="obstore not installed")
class TestExternalStorageCallbacks:
    """Integration tests using a real obstore MemoryStore."""

    async def test_list_entries(self, mocked_kernel: MockedKernel) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("0"),
                    code=(
                        "from obstore.store import MemoryStore\n"
                        f"{STORAGE_VAR} = MemoryStore()"
                    ),
                ),
            ]
        )

        store = k.globals[VariableName(STORAGE_VAR)]
        await store.put_async("data/file1.csv", b"a,b,c")
        await store.put_async("data/file2.txt", b"hello")

        request = StorageListEntriesCommand(
            request_id=RequestId("req-10"),
            namespace=STORAGE_VAR,
            limit=100,
            prefix="data/",
        )
        await k.handle_message(request)

        results = [
            op
            for op in stream.operations
            if isinstance(op, StorageEntriesNotification)
        ]
        assert results == [
            StorageEntriesNotification(
                request_id=RequestId("req-10"),
                entries=[
                    StorageEntry(
                        path="data/file1.csv",
                        kind="object",
                        size=5,
                        last_modified=IsPositiveFloat(),  # pyright: ignore[reportArgumentType]
                        metadata={"e_tag": IsStr()},
                    ),
                    StorageEntry(
                        path="data/file2.txt",
                        kind="object",
                        size=5,
                        last_modified=IsPositiveFloat(),  # pyright: ignore[reportArgumentType]
                        metadata={"e_tag": IsStr()},
                    ),
                ],
                namespace=STORAGE_VAR,
                prefix="data/",
            )
        ]

    async def test_list_entries_with_limit(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("0"),
                    code=(
                        "from obstore.store import MemoryStore\n"
                        f"{STORAGE_VAR} = MemoryStore()"
                    ),
                ),
            ]
        )

        store = k.globals[VariableName(STORAGE_VAR)]
        await store.put_async("a.txt", b"1")
        await store.put_async("b.txt", b"2")
        await store.put_async("c.txt", b"3")

        request = StorageListEntriesCommand(
            request_id=RequestId("req-11"),
            namespace=STORAGE_VAR,
            limit=2,
            prefix=None,
        )
        await k.handle_message(request)

        results = [
            op
            for op in stream.operations
            if isinstance(op, StorageEntriesNotification)
        ]
        assert results == [
            StorageEntriesNotification(
                request_id=RequestId("req-11"),
                entries=[
                    StorageEntry(
                        path="a.txt",
                        kind="object",
                        size=1,
                        last_modified=IsPositiveFloat(),  # pyright: ignore[reportArgumentType]
                        metadata={"e_tag": IsStr()},
                    ),
                    StorageEntry(
                        path="b.txt",
                        kind="object",
                        size=1,
                        last_modified=IsPositiveFloat(),  # pyright: ignore[reportArgumentType]
                        metadata={"e_tag": IsStr()},
                    ),
                ],
                namespace=STORAGE_VAR,
                prefix=None,
            )
        ]

    async def test_list_entries_empty(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("0"),
                    code=(
                        "from obstore.store import MemoryStore\n"
                        f"{STORAGE_VAR} = MemoryStore()"
                    ),
                ),
            ]
        )

        request = StorageListEntriesCommand(
            request_id=RequestId("req-12"),
            namespace=STORAGE_VAR,
            limit=100,
            prefix=None,
        )
        await k.handle_message(request)

        results = [
            op
            for op in stream.operations
            if isinstance(op, StorageEntriesNotification)
        ]
        assert results == [
            StorageEntriesNotification(
                request_id=RequestId("req-12"),
                entries=[],
                namespace=STORAGE_VAR,
                prefix=None,
            )
        ]

    async def test_list_entries_backend_exception(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("0"),
                    code=(
                        "from obstore.store import MemoryStore\n"
                        f"{STORAGE_VAR} = MemoryStore()"
                    ),
                ),
            ]
        )

        # Use a real Obstore backend with a broken list_entries
        store = k.globals[VariableName(STORAGE_VAR)]
        broken_backend = Obstore(store, VariableName(STORAGE_VAR))
        broken_backend.list_entries = MagicMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("connection timeout"),
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                k.external_storage_callbacks,
                "_get_storage_backend",
                lambda _: (broken_backend, None),
            )
            request = StorageListEntriesCommand(
                request_id=RequestId("req-13"),
                namespace=STORAGE_VAR,
                limit=100,
                prefix=None,
            )
            await k.handle_message(request)

        results = [
            op
            for op in stream.operations
            if isinstance(op, StorageEntriesNotification)
        ]
        assert results == [
            StorageEntriesNotification(
                request_id=RequestId("req-13"),
                entries=[],
                namespace=STORAGE_VAR,
                prefix=None,
                error="Failed to list entries: connection timeout",
            )
        ]

    async def test_download(self, mocked_kernel: MockedKernel) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("0"),
                    code=(
                        "from obstore.store import MemoryStore\n"
                        f"{STORAGE_VAR} = MemoryStore()"
                    ),
                ),
            ]
        )

        store = k.globals[VariableName(STORAGE_VAR)]
        await store.put_async("reports/data.csv", b"a,b,c\n1,2,3")

        request = StorageDownloadCommand(
            request_id=RequestId("req-20"),
            namespace=STORAGE_VAR,
            path="reports/data.csv",
        )
        await k.handle_message(request)

        results = [
            op
            for op in stream.operations
            if isinstance(op, StorageDownloadReadyNotification)
        ]
        assert results == [
            StorageDownloadReadyNotification(
                request_id=RequestId("req-20"),
                url=IsStr(),  # pyright: ignore[reportArgumentType]
                filename="data.csv",
            )
        ]

    async def test_download_backend_exception(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("0"),
                    code=(
                        "from obstore.store import MemoryStore\n"
                        f"{STORAGE_VAR} = MemoryStore()"
                    ),
                ),
            ]
        )

        store = k.globals[VariableName(STORAGE_VAR)]
        broken_backend = Obstore(store, VariableName(STORAGE_VAR))
        broken_backend.download_file = AsyncMock(  # type: ignore[method-assign]
            side_effect=PermissionError("access denied"),
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                k.external_storage_callbacks,
                "_get_storage_backend",
                lambda _: (broken_backend, None),
            )
            request = StorageDownloadCommand(
                request_id=RequestId("req-21"),
                namespace=STORAGE_VAR,
                path="secret/file.bin",
            )
            await k.handle_message(request)

        results = [
            op
            for op in stream.operations
            if isinstance(op, StorageDownloadReadyNotification)
        ]
        assert results == [
            StorageDownloadReadyNotification(
                request_id=RequestId("req-21"),
                url=None,
                filename=None,
                error="Failed to download: access denied",
            )
        ]
