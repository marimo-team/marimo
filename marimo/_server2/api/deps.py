# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Annotated, Literal, Optional

from marimo._config.config import MarimoConfig, get_configuration
from marimo._server.model import SessionMode
from marimo._server.sessions import Session, SessionManager, get_manager
from starlette.requests import Request


def get_current_session(request: Request) -> Session:
    """Get the current session."""
    session_id = request.headers["Marimo-Session-Id"]
    return get_manager().sessions[session_id]


# Dependency for getting the current session manager
SessionManagerDep = Annotated[SessionManager, Depends(get_manager)]


# Duplicating _AppConfig because Pydantic complains in Python 3.10 when
# it isn't a Pydantic model
class _AppConfig(BaseModel):
    width: Literal["normal", "full"] = "normal"

    # The file path of the layout file, relative to the app file.
    layout_file: Optional[str] = None


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
        app_config=_AppConfig(
            width=session_manager.app_config.width,
            layout_file=session_manager.app_config.layout_file,
        )
        if session_manager.app_config is not None
        else _AppConfig(width="normal", layout_file=None),
        quiet=session_manager.quiet,
        development_mode=session_manager.development_mode,
    )


# Dependency session manager state
# Just a slimmed down SessionManager that is less leaky
# TODO: is there better naming for this?
SessionManagerStateDep = Annotated[
    SessionManagerState, Depends(get_session_manager_state)
]


# Dependency for getting the current session
# This uses the marimo_session_id header to get the current session
SessionDep = Annotated[Session, Depends(get_current_session)]

# Dependency for getting the user config
UserConfigDep = Annotated[MarimoConfig, Depends(get_configuration)]
