# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._messaging.notification import (
    StorageDownloadReadyNotification,
    StorageEntriesNotification,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.virtual_file.virtual_file import VirtualFile
from marimo._tracer import kernel_tracer
from marimo._types.ids import VariableName

if TYPE_CHECKING:
    from marimo._data._external_storage.models import StorageBackend
    from marimo._runtime.commands import (
        StorageDownloadCommand,
        StorageListEntriesCommand,
    )
    from marimo._runtime.runtime import Kernel

LOGGER = _loggers.marimo_logger()


class ExternalStorageCallbacks:
    def __init__(self, kernel: Kernel):
        self._kernel = kernel

    def _get_storage_backend(
        self, namespace: str
    ) -> tuple[StorageBackend[Any] | None, str | None]:
        """Look up a storage backend by variable name from kernel globals.

        Returns (backend, error). If there is error, backend is None.
        """
        from marimo._data._external_storage.get_storage import STORAGE_BACKENDS

        variable_name = VariableName(namespace)
        if variable_name not in self._kernel.globals:
            return None, f"Variable '{namespace}' not found"

        var = self._kernel.globals[variable_name]

        for backend in STORAGE_BACKENDS:
            if backend.is_compatible(var):
                return backend(var, variable_name), None
        return None, (
            f"Variable '{namespace}' is not a compatible "
            "storage backend (expected obstore or fsspec)"
        )

    _VFILE_TTL_SECONDS = 60

    def _schedule_vfile_cleanup(self, vfile: VirtualFile) -> None:
        """Best-effort cleanup of a virtual file after a TTL."""
        import asyncio

        from marimo._runtime.context import get_context

        try:
            registry = get_context().virtual_file_registry
            loop = asyncio.get_running_loop()
            loop.call_later(self._VFILE_TTL_SECONDS, registry.remove, vfile)
        except Exception:
            LOGGER.debug(
                "Could not schedule virtual file cleanup for %s",
                vfile.filename,
            )

    @kernel_tracer.start_as_current_span("storage_list_entries")
    async def list_entries(self, request: StorageListEntriesCommand) -> None:
        """List storage entries at a given prefix."""
        backend, error = self._get_storage_backend(request.namespace)
        if error is not None or backend is None:
            broadcast_notification(
                StorageEntriesNotification(
                    request_id=request.request_id,
                    entries=[],
                    namespace=request.namespace,
                    prefix=request.prefix,
                    error=error,
                ),
            )
            return

        # list_entries is synchronous, so we wrap it in asyncio.to_thread
        def list_entries() -> list[StorageEntry]:
            return backend.list_entries(
                prefix=request.prefix, limit=request.limit
            )

        try:
            entries = await asyncio.to_thread(list_entries)
            broadcast_notification(
                StorageEntriesNotification(
                    request_id=request.request_id,
                    entries=entries,
                    namespace=request.namespace,
                    prefix=request.prefix,
                ),
            )
        except Exception as e:
            LOGGER.exception(
                "Failed to list entries for %s at prefix %s",
                request.namespace,
                request.prefix,
            )
            broadcast_notification(
                StorageEntriesNotification(
                    request_id=request.request_id,
                    entries=[],
                    namespace=request.namespace,
                    prefix=request.prefix,
                    error=f"Failed to list entries: {e}",
                ),
            )

    _PREVIEW_MAX_BYTES = 1_000_000  # 1 MB

    @kernel_tracer.start_as_current_span("storage_download")
    async def download(self, request: StorageDownloadCommand) -> None:
        """
        Download a storage entry, preferring a signed URL.
        If preview is true, downloads the first 1MB of the file and returns a same-origin virtual file URL.
        """
        backend, error = self._get_storage_backend(request.namespace)
        if error is not None or backend is None:
            broadcast_notification(
                StorageDownloadReadyNotification(
                    request_id=request.request_id,
                    url=None,
                    filename=None,
                    error=error,
                ),
            )
            return

        filename = request.path.rsplit("/", 1)[-1] or "download"

        try:
            if request.preview:
                await self._download_preview(backend, request, filename)
            else:
                await self._download_full(backend, request, filename)
        except Exception as e:
            LOGGER.exception(
                "Failed to download %s from %s",
                request.path,
                request.namespace,
            )
            broadcast_notification(
                StorageDownloadReadyNotification(
                    request_id=request.request_id,
                    url=None,
                    filename=None,
                    error=f"Failed to download: {e}",
                ),
            )

    async def _download_full(
        self,
        backend: StorageBackend[Any],
        request: StorageDownloadCommand,
        filename: str,
    ) -> None:
        signed_url = await backend.sign_download_url(request.path)
        if signed_url is not None:
            broadcast_notification(
                StorageDownloadReadyNotification(
                    request_id=request.request_id,
                    url=signed_url,
                    filename=filename,
                ),
            )
            return

        # Signing not supported; fall back to virtual file with TTL
        result = await backend.download_file(request.path)
        vfile = VirtualFile.create_and_register(result.file_bytes, result.ext)
        self._schedule_vfile_cleanup(vfile)

        broadcast_notification(
            StorageDownloadReadyNotification(
                request_id=request.request_id,
                url=vfile.url,
                filename=result.filename,
            ),
        )

    async def _download_preview(
        self,
        backend: StorageBackend[Any],
        request: StorageDownloadCommand,
        filename: str,
    ) -> None:
        """Read partial content and serve via a virtual file with TTL. This is useful to bypass CORS."""
        data = await backend.read_range(
            request.path, offset=0, length=self._PREVIEW_MAX_BYTES
        )
        _, ext = os.path.splitext(filename)
        vfile = VirtualFile.create_and_register(data, ext.lstrip(".") or "txt")
        self._schedule_vfile_cleanup(vfile)

        broadcast_notification(
            StorageDownloadReadyNotification(
                request_id=request.request_id,
                url=vfile.url,
                filename=filename,
            ),
        )
