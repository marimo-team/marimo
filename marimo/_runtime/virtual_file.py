# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import random
import string
import sys
import threading
from collections.abc import Iterable
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

    def __init__(
        self, filename: str, buffer: bytes, url: Optional[str] = None
    ) -> None:
        self.filename = filename
        self.buffer = buffer
        # Create a file URL with the buffer size
        # This is a hack so when we pull from shared memory we know how
        # many bytes to read.
        self.url = url or f"/@file/{len(buffer)}-{filename}"

    @staticmethod
    def from_external_url(url: str) -> VirtualFile:
        return VirtualFile(
            filename=url,
            buffer=b"",
            url=url,
        )


EMPTY_VIRTUAL_FILE = VirtualFile(
    filename="empty.txt",
    url="/@file/0-empty.txt",
    buffer=b"",
)


class VirtualFileLifecycleItem(CellLifecycleItem):
    def __init__(self, ext: str, buffer: bytes) -> None:
        self.ext = _without_leading_dot(ext)
        self.buffer = buffer
        # Not resolved until added to registry
        self._virtual_file: Optional[VirtualFile] = None

    @property
    def virtual_file(self) -> VirtualFile:
        assert self._virtual_file is not None
        return self._virtual_file

    def create(self, context: "RuntimeContext") -> None:
        """Create the virtual file

        Every virtual file gets a unique random name. Uniqueness is
        required for reference counting.
        """
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

    def dispose(self, context: "RuntimeContext", deletion: bool) -> bool:
        # Remove the file if the refcount is 0, or if the cell is being
        # deleted. (We can't rely on when the refcount will be decremented, so
        # we need to check for deletion explicitly to prevent leaks.)
        if deletion or (
            context.virtual_file_registry.refcount(self.virtual_file.filename)
            <= 0
        ):
            context.virtual_file_registry.remove(self.virtual_file)
            return True
        # refcount > 0, so need to keep this disposal hook around
        return False


@dataclasses.dataclass
class VirtualFileRegistryItem:
    # contents of the file
    shm: shared_memory.SharedMemory
    # number of HTML objects that are referencing this virtual file
    refcount: int


@dataclasses.dataclass
class VirtualFileRegistry:
    """Registry of virtual files

    The registry maps virtual file filenames to their contents. Each
    registry item is reference counted: refcount > 0 means that an object
    exists somewhere that uses the virtual file.

    The registry itself doesn't maintain the reference counts, it only
    exposes methods for incrementing, decrementing, and getting the counts.
    """

    registry: dict[str, VirtualFileRegistryItem] = dataclasses.field(
        default_factory=dict
    )
    shutting_down = False

    def __del__(self) -> None:
        self.shutdown()

    def has(self, filename: str) -> bool:
        return filename in self.registry

    def filenames(self) -> Iterable[str]:
        return self.registry.keys()

    def reference(self, filename: str) -> None:
        """Increment the reference count"""
        if filename in self.registry:
            self.registry[filename].refcount += 1

    def dereference(self, filename: str) -> None:
        """Decrement the reference count"""
        if filename in self.registry:
            self.registry[filename].refcount -= 1

    def refcount(self, filename: str) -> int:
        """Get the reference count"""
        if filename in self.registry:
            return self.registry[filename].refcount
        return 0

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
        # To retrieve the buffer from another process, use:
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
        if sys.platform != "win32":
            # don't call close() on Windows, due to a bug in the Windows
            # Python implementation. On Windows, close() actually unlinks
            # (destroys) the shared_memory:
            # https://stackoverflow.com/questions/63713241/segmentation-fault-using-python-shared-memory/63717188#63717188
            shm.close()
        # We have to keep a reference to the shared memory to prevent it from
        # being destroyed on Windows
        self.registry[key] = VirtualFileRegistryItem(shm=shm, refcount=0)

    def remove(self, virtual_file: VirtualFile) -> None:
        key = virtual_file.filename
        if key in self.registry:
            if sys.platform == "win32":
                self.registry[key].shm.close()
            # destroy the shared memory
            self.registry[key].shm.unlink()
            del self.registry[key]

    def shutdown(self) -> None:
        # Try to make this method re-entrant since it's called in the
        # sigterm handler
        #
        # https://www.gnu.org/software/libc/manual/html_node/Nonreentrancy.html
        if self.shutting_down:
            return
        try:
            self.shutting_down = True
            for _, item in self.registry.items():
                if sys.platform == "win32":
                    item.shm.close()
                item.shm.unlink()
            self.registry.clear()
        finally:
            self.shutting_down = False


def _without_leading_dot(ext: str) -> str:
    return ext[1:] if ext.startswith(".") else ext
