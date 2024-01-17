from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

from marimo._server.sessions import Session, get_manager
from marimo._server2.api.utils import require_header


async def get_current_session(
    marimo_session_id: Annotated[list[str] | None, Header()] = None,
) -> Session:
    header = require_header(marimo_session_id)

    return get_manager().sessions[header]


# Dependency for getting the current session
# This uses the marimo_session_id header to get the current session
SessionDep = Annotated[Session, Depends(get_current_session)]
