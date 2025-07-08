# Copyright 2025 Marimo. All rights reserved.
"""
Async version of pathlib.Path that uses asyncio.to_thread for filesystem operations.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import IO, TYPE_CHECKING, Any, Optional, Union

StrPath = Union[str, os.PathLike[str]]

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator


class AsyncPath(PurePath):
    """
    An async version of pathlib.Path that uses asyncio.to_thread for filesystem operations.

    This class inherits from PurePath for path manipulation and adds async filesystem methods.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> AsyncPath:
        # Create the path using the same logic as PurePath
        if cls is AsyncPath:
            cls = AsyncWindowsPath if os.name == "nt" else AsyncPosixPath
        return super().__new__(cls, *args, **kwargs)  # type: ignore

    def __truediv__(self, other: StrPath) -> AsyncPath:
        # Override to return AsyncPath instance
        result = super().__truediv__(other)
        return self.__class__(result)

    def __rtruediv__(self, other: StrPath) -> AsyncPath:
        # Override to return AsyncPath instance
        result = super().__rtruediv__(other)
        return self.__class__(result)

    @property
    def _path(self) -> Path:
        """Get the synchronous Path equivalent."""
        return Path(self)

    # Async filesystem operations

    async def exists(self) -> bool:
        """Return True if the path exists."""
        return await asyncio.to_thread(self._path.exists)

    async def is_file(self) -> bool:
        """Return True if the path is a regular file."""
        return await asyncio.to_thread(self._path.is_file)

    async def is_dir(self) -> bool:
        """Return True if the path is a directory."""
        return await asyncio.to_thread(self._path.is_dir)

    async def is_symlink(self) -> bool:
        """Return True if the path is a symbolic link."""
        return await asyncio.to_thread(self._path.is_symlink)

    async def stat(self) -> os.stat_result:
        """Return stat info for the path."""
        return await asyncio.to_thread(self._path.stat)

    async def lstat(self) -> os.stat_result:
        """Return lstat info for the path (doesn't follow symlinks)."""
        return await asyncio.to_thread(self._path.lstat)

    async def chmod(self, mode: int) -> None:
        """Change file mode and permissions."""
        return await asyncio.to_thread(self._path.chmod, mode)

    async def unlink(self, missing_ok: bool = False) -> None:
        """Remove the file."""
        return await asyncio.to_thread(self._path.unlink, missing_ok)

    async def rmdir(self) -> None:
        """Remove the directory."""
        return await asyncio.to_thread(self._path.rmdir)

    async def mkdir(
        self, mode: int = 0o777, parents: bool = False, exist_ok: bool = False
    ) -> None:
        """Create directory."""
        return await asyncio.to_thread(
            self._path.mkdir, mode, parents, exist_ok
        )

    async def rename(self, target: Union[str, AsyncPath, Path]) -> AsyncPath:
        """Rename the path to target."""
        result = await asyncio.to_thread(self._path.rename, target)
        return self.__class__(result)

    async def replace(self, target: Union[str, AsyncPath, Path]) -> AsyncPath:
        """Replace the path with target."""
        result = await asyncio.to_thread(self._path.replace, target)
        return self.__class__(result)

    async def symlink_to(
        self, target: Union[str, Path], target_is_directory: bool = False
    ) -> None:
        """Create a symbolic link to target."""
        return await asyncio.to_thread(
            self._path.symlink_to, target, target_is_directory
        )

    async def hardlink_to(self, target: Union[str, Path]) -> None:
        """Create a hard link to target."""
        return await asyncio.to_thread(self._path.hardlink_to, target)

    async def readlink(self) -> AsyncPath:
        """Return the path the symbolic link points to."""
        result = await asyncio.to_thread(self._path.readlink)
        return self.__class__(result)

    # File I/O operations

    async def read_text(
        self, encoding: Optional[str] = None, errors: Optional[str] = None
    ) -> str:
        """Read and return the file contents as text."""
        return await asyncio.to_thread(self._path.read_text, encoding, errors)

    async def read_bytes(self) -> bytes:
        """Read and return the file contents as bytes."""
        return await asyncio.to_thread(self._path.read_bytes)

    async def write_text(
        self,
        data: str,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        newline: Optional[str] = None,
    ) -> int:
        """Write text data to the file."""
        if sys.version_info >= (3, 10):
            return await asyncio.to_thread(
                self._path.write_text, data, encoding, errors, newline
            )
        else:
            return await asyncio.to_thread(
                self._path.write_text, data, encoding, errors
            )

    async def write_bytes(self, data: bytes) -> int:
        """Write bytes data to the file."""
        return await asyncio.to_thread(self._path.write_bytes, data)

    # Directory operations

    async def iterdir(self) -> AsyncGenerator[AsyncPath, None]:
        """Iterate over directory contents asynchronously."""

        def _iterdir() -> Iterator[Path]:
            return self._path.iterdir()

        paths = await asyncio.to_thread(list, _iterdir())
        for path in paths:
            yield self.__class__(path)

    async def glob(self, pattern: str) -> AsyncGenerator[AsyncPath, None]:
        """Glob for paths matching pattern asynchronously."""

        def _glob() -> Iterator[Path]:
            return self._path.glob(pattern)

        paths = await asyncio.to_thread(list, _glob())
        for path in paths:
            yield self.__class__(path)

    async def rglob(self, pattern: str) -> AsyncGenerator[AsyncPath, None]:
        """Recursively glob for paths matching pattern asynchronously."""

        def _rglob() -> Iterator[Path]:
            return self._path.rglob(pattern)

        paths = await asyncio.to_thread(list, _rglob())
        for path in paths:
            yield self.__class__(path)

    # Utility methods

    async def resolve(self, strict: bool = False) -> AsyncPath:
        """Resolve the path to an absolute path."""
        result = await asyncio.to_thread(self._path.resolve, strict)
        return self.__class__(result)

    async def expanduser(self) -> AsyncPath:
        """Expand ~ and ~user constructs."""
        result = await asyncio.to_thread(self._path.expanduser)
        return self.__class__(result)

    # Context manager support for opening files

    def open(
        self,
        mode: str = "r",
        buffering: int = -1,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        newline: Optional[str] = None,
    ) -> IO[Any]:
        """
        Open the file.

        This returns the same file object as the built-in open() function.
        Note: This is not async - use aiofiles or similar for truly async file I/O.
        """
        return self._path.open(mode, buffering, encoding, errors, newline)


class AsyncPosixPath(AsyncPath, PurePosixPath):
    """AsyncPath implementation for POSIX systems."""

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        return super().__getattr__(name)  # type: ignore


class AsyncWindowsPath(AsyncPath, PureWindowsPath):
    """AsyncPath implementation for Windows systems."""

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        return super().__getattr__(name)  # type: ignore
