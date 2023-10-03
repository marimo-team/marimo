# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import io
from multiprocessing import shared_memory
from typing import TYPE_CHECKING, Callable

from marimo._runtime.cell_lifecycle_item import CellLifecycleItem

if TYPE_CHECKING:
    from marimo._runtime.context import RuntimeContext


@dataclasses.dataclass
class VirtualFile:
    url: str

    def __init__(self, filename: str) -> None:
        raise NotImplementedError

    def to_stream(self) -> io.BytesIO:
        raise NotImplementedError


class VirutalFileLifeCycleItem(CellLifecycleItem):
    def __init__(
        self, filename: str, to_stream: Callable[[], io.BytesIO]
    ) -> None:
        self.filename = filename
        self.virtual_file = VirtualFile(self.filename)
        self.to_stream = to_stream

    def create(self, context: "RuntimeContext") -> None:
        context.virtual_file_registry.add(
            self.virtual_file.url, self.virtual_file
        )

    def dispose(self, context: "RuntimeContext") -> None:
        context.virtual_file_registry.remove(self.virtual_file.url)


@dataclasses.dataclass
class VirtualFileRegistry:
    registry: dict[str, shared_memory.SharedMemory] = dataclasses.field(
        default_factory=dict
    )

    def add(self, url: str, virtual_file: VirtualFile) -> None:
        buffer = virtual_file.to_stream().getbuffer()
        # Immediately writes the contents of the file to an in-memory
        # buffer; not lazy.
        #
        # To retrieve the buffer from another proces, use:
        #
        # ```
        # buffer_contents = bytes(shared_memory.SharedMemory(name=url).buf)
        # ```
        shm = shared_memory.SharedMemory(
            name=url,
            create=True,
            size=buffer.nbytes,
        )
        shm.buf[:] = buffer
        self.registry[url] = shm

    def remove(self, url: str) -> None:
        if url in self.registry:
            self.registry[url].unlink()
            del self.registry[url]
