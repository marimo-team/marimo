# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header
from pydantic import BaseModel

from marimo._ast.app import _AppConfig
from marimo._config.config import MarimoConfig, get_configuration
from marimo._server.model import SessionMode
from marimo._server.sessions import Session, SessionManager, get_manager
from marimo._server2.api.utils import require_header

# Dependency for getting the current session manager
SessionManagerDep = Annotated[SessionManager, Depends(get_manager)]


class SessionManagerState(BaseModel):
    server_token: str
    filename: Optional[str]
    mode: SessionMode
    app_config: Optional[_AppConfig]
    quiet: bool
    development_mode: bool


def get_session_manager_state(
    session_manager: SessionManagerDep,
) -> SessionManagerState:
    return SessionManagerState(
        server_token=session_manager.server_token,
        filename=session_manager.filename,
        mode=session_manager.mode,
        app_config=session_manager.app_config,
        quiet=session_manager.quiet,
        development_mode=session_manager.development_mode,
    )


# Dependency session manager state
# Just a slimmed down SessionManager that is less leaky
# TODO: is there better naming for this?
SessionManagerStateDep = Annotated[
    SessionManager, Depends(get_session_manager_state)
]


async def get_current_session(
    session_manager: SessionManagerDep,
    marimo_session_id: Annotated[Optional[list[str]], Header()] = None,
) -> Session:
    header = require_header(marimo_session_id)

    return session_manager.sessions[header]


# Dependency for getting the current session
# This uses the marimo_session_id header to get the current session
SessionDep = Annotated[Session, Depends(get_current_session)]

# Dependency for getting the user config
UserConfigDep = Annotated[MarimoConfig, Depends(get_configuration)]
