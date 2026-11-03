# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

from marimo._server.api.auth import validate_auth
from marimo._server.api.deps import AppState
from marimo._server.codes import WebSocketCloseReason, WebSocketCodes
from marimo._server.workspace import MarimoFileKey
from marimo._types.ids import SessionId

SESSION_QUERY_PARAM_KEY = "session_id"
FILE_QUERY_PARAM_KEY = "file"
KIOSK_QUERY_PARAM_KEY = "kiosk"


@dataclass
class ConnectionParams:
    """Parameters extracted from a session connection request."""

    session_id: SessionId
    file_key: MarimoFileKey
    kiosk: bool
    auto_instantiate: bool


@dataclass
class ConnectionRejection:
    """Why a session connection request was refused.

    Carries the WebSocket close code and reason; non-websocket transports
    translate these into their own close signal.
    """

    code: WebSocketCodes
    reason: WebSocketCloseReason


def parse_connection_params(
    app_state: AppState,
) -> ConnectionParams | ConnectionRejection:
    """Extract and validate session connection parameters.

    Transport-agnostic: reads query params and config from the request held
    by `app_state`.
    """
    # Extract session_id
    raw_session_id = app_state.query_params(SESSION_QUERY_PARAM_KEY)
    if raw_session_id is None:
        return ConnectionRejection(
            WebSocketCodes.NORMAL_CLOSE, WebSocketCloseReason.NO_SESSION_ID
        )

    session_id = SessionId(raw_session_id)

    # Extract file_key
    file_key: MarimoFileKey | None = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or app_state.session_manager.workspace.get_unique_file_key()
    )

    if file_key is None:
        return ConnectionRejection(
            WebSocketCodes.NORMAL_CLOSE, WebSocketCloseReason.NO_FILE_KEY
        )

    # Extract kiosk mode
    kiosk = app_state.query_params(KIOSK_QUERY_PARAM_KEY) == "true"

    # Extract config-based parameters
    config = app_state.config_manager_at_file(file_key).get_config()
    auto_instantiate = config["runtime"]["auto_instantiate"]

    return ConnectionParams(
        session_id=session_id,
        file_key=file_key,
        kiosk=kiosk,
        auto_instantiate=auto_instantiate,
    )


class WebSocketConnectionValidator:
    """Validates and extracts connection parameters from WebSocket requests."""

    def __init__(self, websocket: WebSocket, app_state: AppState):
        self.websocket = websocket
        self.app_state = app_state

    async def validate_auth(self) -> bool:
        """Validate authentication, close socket if invalid.

        Returns:
            True if authentication is valid or not required, False otherwise.
        """
        if self.app_state.enable_auth and not validate_auth(self.websocket):
            await self.websocket.close(
                WebSocketCodes.UNAUTHORIZED, WebSocketCloseReason.UNAUTHORIZED
            )
            return False
        return True

    async def extract_connection_params(
        self,
    ) -> ConnectionParams | None:
        """Extract and validate connection parameters.

        Closes the socket on invalid parameters.

        Returns:
            ConnectionParams if all parameters are valid, None otherwise.
        """
        result = parse_connection_params(self.app_state)
        if isinstance(result, ConnectionRejection):
            await self.websocket.close(result.code, result.reason)
            return None
        return result
