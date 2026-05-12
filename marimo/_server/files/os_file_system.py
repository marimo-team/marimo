# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import tempfile
from collections import deque
from pathlib import Path
from typing import Literal, Protocol

from marimo import _loggers
from marimo._server.files.file_system import FileSystem
from marimo._server.models.files import FileDetailsResponse, FileInfo
from marimo._session.notebook.file_manager import AppFileManager
from marimo._utils.files import natural_sort

LOGGER = _loggers.marimo_logger()

IGNORE_LIST = [
    ".",
    "..",
    ".DS_Store",
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "site-packages",
]

DISALLOWED_NAMES = [
    ".",
    "..",
]

# 1 MiB. Large enough to amortize syscall overhead, small enough to keep
# peak memory bounded when streaming.
_STREAM_CHUNK_SIZE = 1024 * 1024

# Hard cap on streamed uploads. Streaming removes the implicit OOM ceiling
# that buffered uploads had, so without a cap an authenticated client could
# exhaust disk. 1 GiB covers normal notebook-data use cases with margin.
MAX_UPLOAD_BYTES = 1024 * 1024 * 1024


class UploadTooLargeError(ValueError):
    """Raised when a streamed upload exceeds `MAX_UPLOAD_BYTES`.

    Separate type (vs. a bare `ValueError`) so the HTTP layer can map it
    to a 413 response instead of the generic error path.
    """


class AsyncByteSource(Protocol):
    """Anything that can be drained chunk-by-chunk into a file.

    Starlette's `UploadFile` satisfies this; so does any object exposing
    an async `read(size)` returning bytes.
    """

    async def read(self, size: int = -1, /) -> bytes: ...


class OSFileSystem(FileSystem):
    def get_root(self) -> str:
        return os.getcwd()

    def list_files(self, path: str) -> list[FileInfo]:
        files: list[FileInfo] = []
        folders: list[FileInfo] = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.name in IGNORE_LIST:
                        continue
                    try:
                        is_directory = entry.is_dir()
                        entry_stat = entry.stat()
                    except OSError:
                        # do not include files that fail to read
                        # (e.g. recursive/broken symlinks)
                        continue

                    info = FileInfo(
                        id=entry.path,
                        path=entry.path,
                        name=entry.name,
                        is_directory=is_directory,
                        is_marimo_file=not is_directory
                        and self._is_marimo_file(entry.path),
                        last_modified=entry_stat.st_mtime,
                    )
                    if is_directory:
                        folders.append(info)
                    else:
                        files.append(info)
        except OSError:
            pass

        return sorted(folders, key=natural_sort_file) + sorted(
            files, key=natural_sort_file
        )

    def _get_file_info(self, path: str) -> FileInfo:
        stat = os.stat(path)
        is_directory = os.path.isdir(path)
        return FileInfo(
            id=path,
            path=path,
            name=os.path.basename(path),
            is_directory=is_directory,
            is_marimo_file=not is_directory and self._is_marimo_file(path),
            last_modified=stat.st_mtime,
        )

    def get_details(
        self,
        path: str,
        encoding: str | None = None,
        contents: str | None = None,
    ) -> FileDetailsResponse:
        file_info = self._get_file_info(path)
        is_base64 = False
        actual_contents: str | bytes | None
        if file_info.is_directory:
            actual_contents = None
        elif contents is not None:
            actual_contents = contents
        else:
            actual_contents = self.open_file(path, encoding=encoding)
            if isinstance(actual_contents, bytes):
                actual_contents = base64.b64encode(actual_contents).decode(
                    "utf-8"
                )
                is_base64 = True
        mime_type = mimetypes.guess_type(path)[0]
        return FileDetailsResponse(
            file=file_info,
            contents=actual_contents,
            mime_type=mime_type,
            is_base64=is_base64,
        )

    def _is_marimo_file(self, path: str) -> bool:
        file_path = Path(path)
        if file_path.suffix not in (".py", ".md", ".qmd"):
            return False

        from marimo._server.files.directory_scanner import is_marimo_app

        return is_marimo_app(path)

    def open_file(self, path: str, encoding: str | None = None) -> str | bytes:
        file_path = Path(path)
        try:
            return file_path.read_text(encoding=encoding or "utf-8")
        except UnicodeDecodeError:
            return file_path.read_bytes()

    @staticmethod
    def _validate_create_name(name: str) -> None:
        """Reject names that are empty, reserved, or traverse out of the
        parent. Centralized so HTTP, WASM, and streaming paths all share it.
        """
        if name in DISALLOWED_NAMES:
            raise ValueError(
                f"Cannot create file or directory with name {name}"
            )
        if name.strip() == "":
            raise ValueError("Cannot create file or directory with empty name")
        if "/" in name or "\\" in name or "\x00" in name:
            raise ValueError(
                f"Invalid name {name!r}: must not contain path separators "
                "or refer to a parent directory"
            )

    def create_file_or_directory(
        self,
        path: str,
        file_type: Literal["file", "directory", "notebook"],
        name: str,
        contents: bytes | None,
    ) -> FileInfo:
        self._validate_create_name(name)

        full_path = Path(path) / name
        full_path = _generate_unique_path(full_path)

        if file_type == "directory":
            full_path.mkdir(parents=True, exist_ok=True)
        elif file_type == "notebook" and not contents:
            from marimo._convert.converters import MarimoConvert

            full_path.parent.mkdir(parents=True, exist_ok=True)
            # Create a new AppFileManager to get the default notebook code
            # We pass None as filename to get the empty notebook template
            ir = AppFileManager(None).app.to_ir()
            converter = MarimoConvert.from_ir(ir)
            if full_path.suffix in (".md", ".qmd"):
                notebook_code = converter.to_markdown(full_path.name)
            else:
                notebook_code = converter.to_py()
            full_path.write_text(notebook_code, encoding="utf-8")
            contents = notebook_code.encode("utf-8")
        else:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(contents or b"")
        # encoding latin-1 to get an invertible representation of the
        # bytes as a string ...
        return self.get_details(
            str(full_path),
            encoding="latin-1",
            contents=(
                contents.decode("latin-1") if contents is not None else None
            ),
        ).file

    async def stream_create_file(
        self,
        path: str,
        name: str,
        source: AsyncByteSource,
    ) -> FileInfo:
        """Stream-write an uploaded file to disk, chunk by chunk.

        Avoids loading the full payload into memory (the HTTP multipart
        path can otherwise buffer 100 MB at once). Writes to a ``.part``
        temp file and atomically renames on success so a failed upload
        doesn't leave a half-written file at the final path.
        """
        self._validate_create_name(name)

        parent = Path(path)
        os.makedirs(parent, exist_ok=True)

        # Atomically claim the destination with O_CREAT|O_EXCL so concurrent
        # uploads can't both pick the same numbered suffix and clobber each
        # other between `_generate_unique_path` and the final rename.
        full_path = _claim_unique_path(parent / name)

        # `NamedTemporaryFile` gives us a guaranteed-unique sibling path for
        # the in-progress `.part` file (same reasoning as above).
        tmp = tempfile.NamedTemporaryFile(
            dir=full_path.parent,
            prefix=full_path.name + ".",
            suffix=".part",
            delete=False,
        )
        tmp_path = tmp.name
        try:
            # Sync writes are bounded to ~1 MiB per chunk, with an `await`
            # in between; event loop blockage is brief and an async file
            # library would only add a dependency for marginal gain.
            written = 0
            with tmp:
                while chunk := await source.read(_STREAM_CHUNK_SIZE):
                    written += len(chunk)
                    if written > MAX_UPLOAD_BYTES:
                        raise UploadTooLargeError(
                            f"Upload exceeds maximum size of "
                            f"{MAX_UPLOAD_BYTES} bytes"
                        )
                    tmp.write(chunk)
            # Replaces our empty marker at `full_path`. Atomic on POSIX
            # and Windows (Python 3.3+).
            os.replace(tmp_path, full_path)
        except BaseException:
            # Clean up both the `.part` and the reserved empty marker.
            # If `os.replace` already succeeded, the marker is gone and
            # `FileNotFoundError` is the expected outcome there.
            for p in (tmp_path, str(full_path)):
                try:
                    os.unlink(p)
                except FileNotFoundError:
                    pass
            raise

        # Use the metadata-only helper: `get_details` would re-read the
        # file contents (and base64-encode binary), defeating the point of
        # streaming for large uploads.
        return self._get_file_info(str(full_path))

    def delete_file_or_directory(self, path: str) -> bool:
        if os.path.isdir(path):
            safe_rmtree(path)
        else:
            os.remove(path)
        return True

    def copy_file_or_directory(self, path: str, new_path: str) -> FileInfo:
        new_path = str(_generate_unique_path(new_path))
        if not _is_allowed_paths(path, new_path):
            raise ValueError(f"Cannot copy to {new_path}")
        if Path(path).is_dir():
            shutil.copytree(path, new_path)
        else:
            shutil.copy2(path, new_path)
        return self.get_details(new_path).file

    def move_file_or_directory(self, path: str, new_path: str) -> FileInfo:
        if not _is_allowed_paths(path, new_path):
            raise ValueError(f"Cannot rename to {new_path}")
        # Disallow moving to an existing path
        if os.path.exists(new_path):
            raise ValueError(f"Destination path {new_path} already exists")
        safe_move(path, new_path)
        return self.get_details(new_path).file

    def update_file(self, path: str, contents: str) -> FileInfo:
        file_path = Path(path)
        file_path.write_text(contents, encoding="utf-8")
        return self.get_details(path, contents=contents).file

    def search(
        self,
        query: str,
        *,
        path: str | None = None,
        include_directories: bool = True,
        include_files: bool = True,
        depth: int = 3,
        limit: int = 100,
    ) -> list[FileInfo]:
        """Search for files and directories matching a query with high performance."""
        if not query.strip():
            return []

        search_path = path if path is not None else self.get_root()
        if not os.path.exists(search_path):
            return []

        query_lower = query.lower()

        # Compile regex pattern for case-insensitive search
        try:
            pattern = re.compile(re.escape(query_lower))
        except re.error:
            # If regex compilation fails, fall back to simple string matching
            pattern = None

        results: list[FileInfo] = []
        seen_paths: set[str] = set()

        # Use BFS with deque for better performance than recursive DFS
        queue = deque([(search_path, 0)])  # (path, current_depth)

        while queue and len(results) < limit:
            current_path, current_depth = queue.popleft()

            # Skip if we've exceeded depth limit
            if current_depth > depth:
                continue

            # Skip if we've already processed this path (avoid symlink loops)
            if current_path in seen_paths:
                continue
            seen_paths.add(current_path)

            try:
                # Use os.scandir for better performance than os.listdir
                with os.scandir(current_path) as entries:
                    for entry in entries:
                        if len(results) >= limit:
                            break

                        # Skip ignored files/directories
                        if entry.name in IGNORE_LIST:
                            continue

                        # Check if name matches query
                        name_lower = entry.name.lower()

                        matches = False
                        if pattern:
                            matches = pattern.search(name_lower) is not None
                        else:
                            matches = query_lower in name_lower

                        if not matches:
                            # If this is a directory and we haven't hit depth limit, add to queue
                            if current_depth < depth:
                                try:
                                    if entry.is_dir():
                                        queue.append(
                                            (entry.path, current_depth + 1)
                                        )
                                except OSError:
                                    # Skip entries that can't be accessed
                                    continue
                            continue

                        try:
                            is_directory = entry.is_dir()
                            entry_stat = entry.stat()

                            # Apply directory/file filtering
                            if not include_directories and is_directory:
                                # Skip directories if directory=False
                                continue
                            if not include_files and not is_directory:
                                # Skip files if file=False
                                continue

                            file_info = FileInfo(
                                id=entry.path,
                                path=entry.path,
                                name=entry.name,
                                is_directory=is_directory,
                                # This can be expensive, so we don't do it on search
                                is_marimo_file=False,
                                last_modified=entry_stat.st_mtime,
                            )
                            results.append(file_info)

                            # If this is a matching directory and we haven't hit depth limit, add to queue
                            if is_directory and current_depth < depth:
                                queue.append((entry.path, current_depth + 1))

                        except OSError:
                            # Skip files/directories that can't be accessed
                            continue

            except OSError:
                # Skip directories that can't be accessed
                continue

        # Sort results by relevance (exact matches first, then by name)
        def sort_key(file_info: FileInfo) -> tuple[int, str]:
            name_lower = file_info.name.lower()

            # Exact match gets highest priority
            if name_lower == query_lower:
                return (0, file_info.name)
            # Starts with query gets second priority
            elif name_lower.startswith(query_lower):
                return (1, file_info.name)
            # Contains query gets lowest priority
            else:
                return (2, file_info.name)

        results.sort(key=sort_key)
        return results[:limit]

    def open_in_editor(self, path: str, line_number: int | None) -> bool:
        try:
            # First try to get editor from environment variable
            editor = os.environ.get("EDITOR")

            # If editor is a terminal-based editor, we just call `open`, because
            # otherwise it silently opens the terminal in the same window that is
            # running marimo.
            if editor and not _is_terminal_editor(editor):
                args = (
                    [path]
                    if line_number is None
                    else editor_open_file_in_line_args(
                        editor, path, line_number
                    )
                )

                try:
                    # For GUI editors
                    subprocess.run([editor, *args])
                    return True
                except Exception as e:
                    LOGGER.error(f"Error opening with EDITOR: {e}")

            # Use system default if no editor specified
            if platform.system() == "Darwin":  # macOS
                subprocess.call(("open", path))
            elif platform.system() == "Windows":  # Windows
                # startfile only exists on Windows
                os.startfile(path)  # type: ignore[attr-defined]
            else:  # Linux variants
                subprocess.call(("xdg-open", path))
            return True
        except Exception as e:
            LOGGER.error(f"Error opening file: {e}")
            return False


def editor_open_file_in_line_args(
    editor: str, path: str, line_number: int
) -> list[str]:
    if editor == "code":
        return ["--goto", f"{path}:{line_number}"]
    elif editor == "subl":
        return [f"{path}:{line_number}"]
    else:
        return [f"+{line_number}", path]


def natural_sort_file(file: FileInfo) -> list[int | str]:
    return natural_sort(file.name)


def _is_terminal_editor(editor: str) -> bool:
    return any(
        ed in editor.lower()
        for ed in [
            "vim",
            "vi",
            "emacs",
            "nano",
            "nvim",
            "neovim",
            "pico",
            "micro",
        ]
    )


def safe_rmtree(path: str) -> None:
    """
    Remove a directory tree. If shutil.rmtree fails, recursively delete all files from the leaves up.

    This is so we can be compatible with https://github.com/awslabs/mountpoint-s3.
    """
    try:
        shutil.rmtree(path)
    except PermissionError:
        # Fallback: manual post-order traversal
        p = Path(path)
        for sub in sorted(
            p.rglob("*"), key=lambda x: -x.as_posix().count("/")
        ):
            try:
                if sub.is_file() or sub.is_symlink():
                    sub.unlink()
                elif sub.is_dir():
                    sub.rmdir()
            except Exception as inner_e:
                LOGGER.warning("Failed to delete %s: %s", sub, inner_e)
        try:
            p.rmdir()
        except Exception as final_e:
            LOGGER.warning("Failed to delete directory %s: %s", p, final_e)


def safe_move(src: str, dst: str) -> None:
    """
    Move a file or directory, but if it fails due to permissions,
    copy the file or directory and then delete the original.

    This is so we can be compatible with https://github.com/awslabs/mountpoint-s3.
    """
    try:
        shutil.move(src, dst)
    except PermissionError:
        # Fallback: copy then delete
        src_path = Path(src)
        if src_path.is_dir():
            shutil.copytree(src, dst)
            safe_rmtree(src)
        else:
            shutil.copy2(src, dst)
            src_path.unlink()


def _generate_unique_path(new_path: str | Path) -> Path:
    # If the file already exists, generate a new name
    new_path = Path(new_path)
    if not new_path.exists():
        return new_path
    i = 1
    name_without_extension = new_path.stem
    extension = new_path.suffix
    while True:
        new_name = f"{name_without_extension}_{i}{extension}"
        new_path = new_path.parent / new_name
        if not new_path.exists():
            return new_path
        i += 1


def _claim_unique_path(target: Path) -> Path:
    """Like `_generate_unique_path`, but atomically reserves the chosen name.

    Opens with O_CREAT|O_EXCL so two concurrent callers can never end up
    with the same path — whichever loses the race sees `FileExistsError`
    and tries the next numbered suffix. Returns the claimed path (an empty
    file at that location); the caller is responsible for writing into it
    (or replacing it).
    """
    name_without_extension = target.stem
    extension = target.suffix
    candidate = target
    i = 0
    while True:
        try:
            fd = os.open(
                candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644
            )
            os.close(fd)
            return candidate
        except FileExistsError:
            i += 1
            candidate = target.parent / (
                f"{name_without_extension}_{i}{extension}"
            )


def _is_allowed_paths(path: str | Path, new_path: str | Path) -> bool:
    file_name = os.path.basename(new_path)
    if file_name in DISALLOWED_NAMES or not file_name.strip():
        return False

    src = Path(path).resolve()
    dst = Path(new_path).resolve()
    return not (src.is_dir() and dst.is_relative_to(src))
