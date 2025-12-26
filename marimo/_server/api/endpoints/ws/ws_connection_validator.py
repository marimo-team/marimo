# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

from marimo import _loggers
from marimo._server.api.auth import validate_auth
from marimo._server.api.deps import AppState
from marimo._server.codes import WebSocketCodes
from marimo._server.file_router import MarimoFileKey
from marimo._types.ids import SessionId

LOGGER = _loggers.marimo_logger()

SESSION_QUERY_PARAM_KEY = "session_id"
FILE_QUERY_PARAM_KEY = "file"
KIOSK_QUERY_PARAM_KEY = "kiosk"


@dataclass
class ConnectionParams:
    """Parameters extracted from WebSocket connection request."""

    session_id: SessionId
    file_key: MarimoFileKey
    kiosk: bool
    auto_instantiate: bool
    rtc_enabled: bool


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
                WebSocketCodes.UNAUTHORIZED, "MARIMO_UNAUTHORIZED"
            )
            return False
        return True

    async def extract_connection_params(
        self,
    ) -> Optional[ConnectionParams]:
        """Extract and validate connection parameters.

        Returns:
            ConnectionParams if all parameters are valid, None otherwise.
        """
        # Extract session_id
        raw_session_id = self.app_state.query_params(SESSION_QUERY_PARAM_KEY)
        if raw_session_id is None:
            await self.websocket.close(
                WebSocketCodes.NORMAL_CLOSE, "MARIMO_NO_SESSION_ID"
            )
            return None

        session_id = SessionId(raw_session_id)

        # Extract file_key
        file_key: Optional[MarimoFileKey] = (
            self.app_state.query_params(FILE_QUERY_PARAM_KEY)
            or self.app_state.session_manager.file_router.get_unique_file_key()
        )

        if file_key is None:
            await self.websocket.close(
                WebSocketCodes.NORMAL_CLOSE, "MARIMO_NO_FILE_KEY"
            )
            return None

        # Extract kiosk mode
        kiosk = self.app_state.query_params(KIOSK_QUERY_PARAM_KEY) == "true"

        # Extract config-based parameters
        config = self.app_state.config_manager_at_file(file_key).get_config()
        rtc_enabled = config.get("experimental", {}).get("rtc_v2", False)
        auto_instantiate = config["runtime"]["auto_instantiate"]

        return ConnectionParams(
            session_id=session_id,
            file_key=file_key,
            kiosk=kiosk,
            auto_instantiate=auto_instantiate,
            rtc_enabled=rtc_enabled,
        )

    async def extract_file_key_only(self) -> Optional[MarimoFileKey]:
        """Extract only the file_key parameter (for RTC endpoint).

        Returns:
            MarimoFileKey if valid, None otherwise.
        """
        file_key: Optional[MarimoFileKey] = (
            self.app_state.query_params(FILE_QUERY_PARAM_KEY)
            or self.app_state.session_manager.file_router.get_unique_file_key()
        )

        if file_key is None:
            LOGGER.warning("RTC: Closing websocket - no file key")
            await self.websocket.close(
                WebSocketCodes.NORMAL_CLOSE, "MARIMO_NO_FILE_KEY"
            )
            return None

        return file_key
