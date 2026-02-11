# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from dirty_equals import IsPositiveFloat
from inline_snapshot import snapshot

from marimo._dependencies.dependencies import DependencyManager
from marimo._storage.get_storage import (
    get_storage_backends_from_variables,
    storage_backend_to_storage_namespace,
)
from marimo._storage.models import StorageEntry, StorageNamespace
from marimo._storage.storage import FsspecFilesystem, Obstore
from marimo._types.ids import VariableName

HAS_OBSTORE = DependencyManager.obstore.has()
HAS_FSSPEC = DependencyManager.fsspec.has()


class TestGetStorageBackendsFromVariables:
    def test_empty_variables(self) -> None:
        result = get_storage_backends_from_variables([])
        assert result == []

    def test_no_compatible_variables(self) -> None:
        variables: list[tuple[VariableName, object]] = [
            (VariableName("x"), "just a string"),
            (VariableName("y"), 42),
            (VariableName("z"), [1, 2, 3]),
        ]
        result = get_storage_backends_from_variables(variables)
        assert result == []

    @pytest.mark.skipif(not HAS_OBSTORE, reason="obstore not installed")
    def test_detects_obstore(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        variables: list[tuple[VariableName, object]] = [
            (VariableName("my_store"), store),
        ]
        result = get_storage_backends_from_variables(variables)
        assert len(result) == 1
        var_name, backend = result[0]
        assert var_name == "my_store"
        assert isinstance(backend, Obstore)

    @pytest.mark.skipif(not HAS_FSSPEC, reason="fsspec not installed")
    def test_detects_fsspec(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        variables: list[tuple[VariableName, object]] = [
            (VariableName("mem_fs"), fs),
        ]
        result = get_storage_backends_from_variables(variables)
        assert len(result) == 1
        var_name, backend = result[0]
        assert var_name == "mem_fs"
        assert isinstance(backend, FsspecFilesystem)

    @pytest.mark.skipif(
        not (HAS_OBSTORE and HAS_FSSPEC),
        reason="obstore and fsspec both required",
    )
    def test_detects_multiple_backends(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem
        from obstore.store import MemoryStore

        ob_store = MemoryStore()
        fs = MemoryFileSystem()

        variables: list[tuple[VariableName, object]] = [
            (VariableName("ob"), ob_store),
            (VariableName("not_storage"), "hello"),
            (VariableName("fs"), fs),
        ]
        result = get_storage_backends_from_variables(variables)
        assert len(result) == 2

        names = [name for name, _ in result]
        assert VariableName("ob") in names
        assert VariableName("fs") in names

        types = [type(backend) for _, backend in result]
        assert Obstore in types
        assert FsspecFilesystem in types

    def test_mixed_with_none_values(self) -> None:
        variables: list[tuple[VariableName, object]] = [
            (VariableName("n"), None),
            (VariableName("d"), {"key": "value"}),
        ]
        result = get_storage_backends_from_variables(variables)
        assert result == []


class TestStorageBackendToStorageNamespace:
    def test_converts_backend_to_namespace(self) -> None:
        mock_backend: Any = MagicMock()
        mock_backend.variable_name = VariableName("test_store")
        mock_backend.protocol = "s3"
        mock_backend.root_path = "my-bucket"
        mock_backend.list_entries.return_value = [
            StorageEntry(
                path="file1.txt",
                size=100,
                last_modified=1700000000.0,
                kind="object",
                metadata={},
            ),
        ]

        result = storage_backend_to_storage_namespace(mock_backend)

        assert result == snapshot(
            StorageNamespace(
                name=VariableName("test_store"),
                display_name="test_store",
                protocol="s3",
                root_path="my-bucket",
                storage_entries=[
                    StorageEntry(
                        path="file1.txt",
                        size=100,
                        last_modified=1700000000.0,
                        kind="object",
                        metadata={},
                    ),
                ],
            )
        )
        mock_backend.list_entries.assert_called_once_with(prefix="")

    def test_handles_none_variable_name(self) -> None:
        mock_backend: Any = MagicMock()
        mock_backend.variable_name = None
        mock_backend.protocol = "file"
        mock_backend.root_path = "/tmp"
        mock_backend.list_entries.return_value = []

        result = storage_backend_to_storage_namespace(mock_backend)

        assert result == snapshot(
            StorageNamespace(
                name=None,
                display_name="",
                protocol="file",
                root_path="/tmp",
                storage_entries=[],
            )
        )

    def test_handles_none_root_path(self) -> None:
        mock_backend: Any = MagicMock()
        mock_backend.variable_name = VariableName("mem")
        mock_backend.protocol = "in-memory"
        mock_backend.root_path = None
        mock_backend.list_entries.return_value = []

        result = storage_backend_to_storage_namespace(mock_backend)

        assert result == snapshot(
            StorageNamespace(
                name=VariableName("mem"),
                display_name="mem",
                protocol="in-memory",
                root_path="",
                storage_entries=[],
            )
        )

    @pytest.mark.skipif(not HAS_FSSPEC, reason="fsspec not installed")
    def test_with_real_fsspec_backend(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        fs.pipe("/hello.txt", b"hi")

        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        result = storage_backend_to_storage_namespace(backend)

        assert result == snapshot(
            StorageNamespace(
                name=VariableName("mem_fs"),
                display_name="mem_fs",
                protocol="memory",
                root_path="/",
                storage_entries=[
                    StorageEntry(
                        path="/hello.txt",
                        kind="file",
                        size=2,
                        last_modified=None,
                        metadata={"created": IsPositiveFloat()},
                    )
                ],
            )
        )

    @pytest.mark.skipif(not HAS_OBSTORE, reason="obstore not installed")
    def test_with_real_obstore_backend(self) -> None:
        import asyncio

        from obstore.store import MemoryStore

        store = MemoryStore()
        asyncio.get_event_loop().run_until_complete(
            store.put_async("test.txt", b"data")
        )

        backend = Obstore(store, VariableName("mem_store"))
        result = storage_backend_to_storage_namespace(backend)

        assert result == snapshot(
            StorageNamespace(
                name=VariableName("mem_store"),
                display_name="mem_store",
                protocol="in-memory",
                root_path="",
                storage_entries=[
                    StorageEntry(
                        path="test.txt",
                        kind="object",
                        size=4,
                        last_modified=IsPositiveFloat(),  # pyright: ignore[reportArgumentType]
                        metadata={"e_tag": "0"},
                    )
                ],
            )
        )
