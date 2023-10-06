# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import random
import string
import threading
from multiprocessing import shared_memory
from typing import TYPE_CHECKING, Optional

from marimo import _loggers
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem

if TYPE_CHECKING:
    from marimo._runtime.context import RuntimeContext

LOGGER = _loggers.marimo_logger()


_ALPHABET = string.ascii_letters + string.digits


def random_filename(ext: str) -> str:
    # adapted from: https://stackoverflow.com/questions/13484726/safe-enough-8-character-short-unique-random-string  # noqa: E501
    # TODO(akshayka): should callers redraw if they get a collision?
    tid = str(threading.get_native_id())
    basename = tid + "-" + "".join(random.choices(_ALPHABET, k=8))
    return f"{basename}.{ext}"


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
    def __init__(self, ext: str, buffer: bytes) -> None:
        self.ext = ext
        self.buffer = buffer
        # Not resolved until added to registry
        self._virtual_file: Optional[VirtualFile] = None

    @property
    def virtual_file(self) -> VirtualFile:
        assert self._virtual_file is not None
        return self._virtual_file

    def create(self, context: "RuntimeContext") -> None:
        filename = random_filename(self.ext)
        registry = context.virtual_file_registry
        # create a unique filename for the virtual file
        tries = 0
        max_tries = 100
        while registry.has(filename) and tries < max_tries:
            filename = random_filename(self.ext)
            tries += 1
        if tries > max_tries:
            raise RuntimeError(
                "Failed to add virtual file to registry. "
                "This is a bug in marimo. Please file an issue."
            )
        self._virtual_file = VirtualFile(filename, self.buffer)
        context.virtual_file_registry.add(self._virtual_file)

    def dispose(self, context: "RuntimeContext") -> None:
        context.virtual_file_registry.remove(self.virtual_file)


@dataclasses.dataclass
class VirtualFileRegistry:
    registry: dict[str, shared_memory.SharedMemory] = dataclasses.field(
        default_factory=dict
    )

    def __del__(self) -> None:
        self.shutdown()

    def has(self, filename: str) -> bool:
        return filename in self.registry

    def add(self, virtual_file: VirtualFile) -> None:
        key = virtual_file.filename
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
        # we can safely close this shm, since we don't need to access its
        # buffer; we do need to keep it around so we can unlink it later
        shm.close()
        self.registry[key] = shm

    def remove(self, virtual_file: VirtualFile) -> None:
        key = virtual_file.filename
        if key in self.registry:
            # destroy the shared memory
            self.registry[key].unlink()
            del self.registry[key]

    def shutdown(self) -> None:
        for _, shm in self.registry.items():
            shm.unlink()
        self.registry.clear()
