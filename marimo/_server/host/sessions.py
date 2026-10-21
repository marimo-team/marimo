# Copyright 2026 Marimo. All rights reserved.
"""Private notebook identities for independently running app sessions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from marimo._core import protocol
from marimo._core.errors import NotFound
from marimo._core.ids import mint

if TYPE_CHECKING:
    from marimo._core.host import Host, NotebookInitializer
    from marimo._session.session import Session


class AppSessionNotebooks:
    """Register actual app sessions without indexing their source files."""

    def __init__(self, host: Host, initialize: NotebookInitializer) -> None:
        self._host = host
        self._initialize = initialize
        self._sessions: dict[protocol.NotebookId, Session] = {}
        self._project_id = mint(protocol.ProjectId, "proj")
        host.update_project(
            protocol.Project(
                id=self._project_id,
                name="app",
                root=None,
                status="indexed",
                message=None,
                operations=(),
            )
        )

    def register(self, session: Session) -> protocol.NotebookId:
        for notebook_id, candidate in self._sessions.items():
            if candidate is session:
                return notebook_id
        notebook_id = mint(protocol.NotebookId, "nb")
        self._sessions[notebook_id] = session
        path = session.app_file_manager.path
        self._host.add_notebook(
            protocol.Notebook(
                id=notebook_id,
                project_id=self._project_id,
                path=None,
                name=Path(path).stem if path else "app",
                updated_at=None,
                operations=(),
            ),
            self._initialize,
        )
        return notebook_id

    def session(self, notebook_id: protocol.NotebookId) -> Session:
        try:
            return self._sessions[notebook_id]
        except KeyError:
            raise NotFound(f"no notebook {notebook_id}") from None

    def remove(self, session: Session) -> None:
        for notebook_id, candidate in list(self._sessions.items()):
            if candidate is session:
                del self._sessions[notebook_id]
                self._host.remove_notebook(notebook_id)
