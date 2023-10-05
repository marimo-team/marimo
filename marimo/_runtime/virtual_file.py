# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
from multiprocessing import shared_memory
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem

if TYPE_CHECKING:
    from marimo._runtime.context import RuntimeContext

LOGGER = _loggers.marimo_logger()


@dataclasses.dataclass
class VirtualFile:
    url: str
    filename: str
    buffer: bytes

    def __init__(self, filename: str, buffer: bytes) -> None:
        self.filename = filename
        self.url = f"/@file/{filename}"
        self.buffer = buffer


class VirtualFileLifecycleItem(CellLifecycleItem):
    def __init__(self, filename: str, buffer: bytes) -> None:
        self.filename = filename
        self.virtual_file = VirtualFile(self.filename, buffer)

    def create(self, context: "RuntimeContext") -> None:
        context.virtual_file_registry.add(self.virtual_file)

    def dispose(self, context: "RuntimeContext") -> None:
        context.virtual_file_registry.remove(self.virtual_file)


@dataclasses.dataclass
class VirtualFileRegistry:
    registry: dict[str, shared_memory.SharedMemory] = dataclasses.field(
        default_factory=dict
    )

    def __del__(self) -> None:
        self.shutdown()

    def _key(self, vfile: VirtualFile) -> str:
        return vfile.filename

    def add(self, virtual_file: VirtualFile) -> None:
        key = self._key(virtual_file)
        if key in self.registry:
            LOGGER.debug(
                "Virtual file (key=%s) already registered", virtual_file
            )
            return

        buffer = virtual_file.buffer
        # Immediately writes the contents of the file to an in-memory
        # buffer; not lazy.
        #
        # To retrieve the buffer from another proces, use:
        #
        # ```
        # try:
        #   shm = shared_memory.SharedMemory(name=key)
        #   buffer_contents = bytes(shm.buf)
        # except FileNotFoundError:
        #   # virtual file was removed
        # ```
        shm = shared_memory.SharedMemory(
            name=key,
            create=True,
            size=len(buffer),
        )
        shm.buf[: len(buffer)] = buffer
        shm.close()
        self.registry[key] = shm

    def remove(self, virtual_file: VirtualFile) -> None:
        key = self._key(virtual_file)
        if key in self.registry:
            # destroy the shared memory
            self.registry[key].unlink()
            del self.registry[key]

    def shutdown(self) -> None:
        for _, shm in self.registry.items():
            shm.unlink()
        self.registry.clear()
