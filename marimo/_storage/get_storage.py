# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._storage.models import StorageBackend, StorageNamespace
from marimo._storage.storage import FsspecFilesystem, Obstore
from marimo._types.ids import VariableName

STORAGE_BACKENDS: list[type[StorageBackend[Any]]] = [Obstore, FsspecFilesystem]


def get_storage_backends_from_variables(
    variables: list[tuple[VariableName, object]],
) -> list[tuple[VariableName, StorageBackend[Any]]]:
    storage_backends: list[tuple[VariableName, StorageBackend[Any]]] = []
    for variable_name, value in variables:
        for storage_backend in STORAGE_BACKENDS:
            if storage_backend.is_compatible(value):
                storage_backends.append(
                    (variable_name, storage_backend(value, variable_name))
                )
                break
    return storage_backends


def storage_backend_to_storage_namespace(
    storage_backend: StorageBackend[Any],
) -> StorageNamespace:
    return StorageNamespace(
        name=storage_backend.variable_name,
        display_name=storage_backend.variable_name or "",
        source=storage_backend.protocol,
        root_path=storage_backend.root_path or "",
        storage_entries=storage_backend.list_entries(prefix=""),
    )
