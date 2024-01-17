from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from pydantic import BaseModel

from marimo._ast.app import _AppConfig
from marimo._server.model import SessionMode
from marimo._server.sessions import Session, SessionManager, get_manager
from marimo._server2.api.utils import require_header

# Dependency for getting the current session manager
SessionManagerDep = Annotated[SessionManager, Depends(get_manager)]


class SessionManagerState(BaseModel):
    server_token: str
    filename: str | None
    mode: SessionMode
    app_config: _AppConfig | None


def get_session_manager_state(
    session_manager: SessionManagerDep,
) -> SessionManagerState:
    return SessionManagerState(
        server_token=session_manager.server_token,
        filename=session_manager.filename,
        mode=session_manager.mode,
        app_config=session_manager.app_config,
    )


# Dependency session manager state
# Just a slimmed down SessionManager that is less leaky
# TODO: is there better naming for this?
SessionManagerStateDep = Annotated[
    SessionManager, Depends(get_session_manager_state)
]


async def get_current_session(
    session_manager: SessionManagerDep,
    marimo_session_id: Annotated[list[str] | None, Header()] = None,
) -> Session:
    header = require_header(marimo_session_id)

    return session_manager.sessions[header]


# Dependency for getting the current session
# This uses the marimo_session_id header to get the current session
SessionDep = Annotated[Session, Depends(get_current_session)]
