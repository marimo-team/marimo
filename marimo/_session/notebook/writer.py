# Copyright 2026 Marimo. All rights reserved.
"""Write notebook sources to a file, remembering what was written."""

from __future__ import annotations

import threading
from contextlib import nullcontext
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._ast.names import DEFAULT_CELL_NAME
from marimo._environments.script_metadata import (
    notebook_file_lock,
    with_python_version_requirement,
)
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    Header,
    NotebookSerializationV1,
)
from marimo._session.notebook.serializer import get_notebook_serializer
from marimo._session.notebook.storage import (
    FilesystemStorage,
    StorageInterface,
)
from marimo._utils.generated_with import (
    contents_differ_excluding_generated_with,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from marimo._messaging.notebook.document import NotebookCell

LOGGER = _loggers.marimo_logger()


def cells_to_ir(
    cells: Iterable[NotebookCell],
    app_config: Mapping[str, Any],
    *,
    header: str | None = None,
) -> NotebookSerializationV1:
    """The serialization of these cells, app options, and loaded header.

    The writer prefers the current file's header and sets the filename.
    """
    return NotebookSerializationV1(
        header=Header(value=header) if header else None,
        app=AppInstantiation(options=dict(app_config)),
        cells=[
            CellDef(
                code=cell.code,
                name=cell.name or DEFAULT_CELL_NAME,
                options=cell.config.asdict(),
            )
            for cell in cells
        ],
    )


class NotebookWriter:
    """Serializes notebook IR to a file and remembers the text last written.

    Share one writer between everything that writes a notebook file, so a
    watcher can tell the notebook's own writes from someone else's, and a
    write whose text is already on disk is skipped.
    """

    def __init__(self, storage: StorageInterface | None = None) -> None:
        self.storage: StorageInterface = storage or FilesystemStorage()
        # Reentrant so a caller can wrap several writes in one critical
        # section while each write re-acquires for direct callers.
        self.lock = threading.RLock()
        self.last_content: str | None = None

    def write_ir(
        self,
        path: Path,
        *,
        notebook: NotebookSerializationV1,
        persist: bool,
        previous_path: Path | None = None,
    ) -> str:
        """Serialize `notebook` for `path` and, if `persist`, write it.

        The file's header is kept, read from `previous_path` when the file
        is being renamed. Returns the text written, or the text already on
        disk when the serialization matches the last write.
        """
        LOGGER.debug("Saving notebook to %s", path)

        # Read the header and write the cells under the same lock as manifest
        # edits, so neither writer can restore the other's stale contents.
        file_lock = notebook_file_lock(str(path)) if persist else nullcontext()
        with self.lock, file_lock:
            # Get the header in case it was modified by the user (e.g. package installation)
            handler = get_notebook_serializer(path)
            header: str | None = None
            if previous_path and previous_path.exists():
                header = handler.extract_header(previous_path)
            elif path.exists():
                header = handler.extract_header(path)

            # For new .py files in sandbox mode, generate header with marimo
            if header is None and str(path).endswith(".py"):
                from marimo._config.settings import GLOBAL_SETTINGS

                if GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
                    from marimo._environments import script_metadata

                    header = script_metadata.dumps(
                        with_python_version_requirement(
                            {
                                "dependencies": ["marimo"],
                            }
                        )
                    )

            # Rewrap with header if relevant and set filename.
            notebook = NotebookSerializationV1(
                app=notebook.app,
                header=Header(value=header) if header else notebook.header,
                cells=notebook.cells,
                violations=notebook.violations,
                valid=notebook.valid,
                filename=str(path),
            )
            contents = handler.serialize(notebook)

            if persist:
                if self.content_matches_last_save(contents):
                    return self.last_content or contents
                self.storage.write(path, contents)
                self.remember(contents)

            return contents

    def remember(self, content: str) -> None:
        """Record `content` as what is on disk, after a write or a reload."""
        with self.lock:
            self.last_content = content.strip()

    def content_matches_last_save(self, content: str) -> bool:
        """Whether `content` is what this writer last wrote or reloaded.

        Differences in the `__generated_with` version alone do not count.
        """
        with self.lock:
            baseline = self.last_content
            if baseline is None:
                return False
            if content.strip() == baseline:
                return True
            return not contents_differ_excluding_generated_with(
                content, baseline
            )
