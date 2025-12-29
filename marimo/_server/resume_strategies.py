# Copyright 2026 Marimo. All rights reserved.
"""Session resume strategies for different modes.

Provides mode-specific logic for determining whether and how to resume sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Protocol

from marimo import _loggers
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.session import Session
from marimo._session.session_repository import SessionRepository
from marimo._types.ids import SessionId

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from marimo._server.file_router import MarimoFileKey


class SessionResumeStrategy(Protocol):
    """Protocol for session resume strategies."""

    def try_resume(
        self,
        new_session_id: SessionId,
        file_key: MarimoFileKey,
    ) -> Optional[Session]:
        """Try to resume a session.

        Args:
            new_session_id: The new session ID to assign
            file_key: The file key for the session

        Returns:
            The resumed session if successful, None otherwise
        """
        ...


class EditModeResumeStrategy(SessionResumeStrategy):
    """Resume strategy for edit mode.

    In edit mode, we can resume orphaned sessions for the same file.
    Only one session per file is allowed in edit mode.
    """

    def __init__(self, repository: SessionRepository) -> None:
        self._repository = repository

    def try_resume(
        self,
        new_session_id: SessionId,
        file_key: MarimoFileKey,
    ) -> Optional[Session]:
        """Try to resume an orphaned session for the same file."""
        import os

        # Find sessions with the same file
        sessions_with_file = []
        for session in self._repository.get_all():
            session_id = self._repository.get_session_id(session)
            if session_id and session.app_file_manager.path == os.path.abspath(
                file_key
            ):
                sessions_with_file.append((session_id, session))

        if len(sessions_with_file) == 0:
            return None

        if len(sessions_with_file) > 1:
            from marimo._server.exceptions import InvalidSessionException

            raise InvalidSessionException(
                "Only one session should exist while editing"
            )

        session_id, session = sessions_with_file[0]
        connection_state = session.connection_state()

        if connection_state == ConnectionState.ORPHANED:
            LOGGER.debug(
                f"Found a resumable EDIT session: prev_id={session_id}"
            )
            # Update session ID
            self._repository.update_session_id_sync(session_id, new_session_id)
            return session

        LOGGER.debug(
            "Session is not resumable, current state: %s",
            connection_state,
        )
        return None


class RunModeResumeStrategy(SessionResumeStrategy):
    """Resume strategy for run mode.

    In run mode, we can only resume if the session ID matches and it's orphaned.
    Multiple sessions can exist for the same file in run mode.
    """

    def __init__(self, repository: SessionRepository) -> None:
        self._repository = repository

    def try_resume(
        self,
        new_session_id: SessionId,
        file_key: MarimoFileKey,  # noqa: ARG002
    ) -> Optional[Session]:
        """Try to resume a session with matching ID if orphaned."""
        session = self._repository.get_sync(new_session_id)

        if session and session.connection_state() == ConnectionState.ORPHANED:
            LOGGER.debug(
                "Found a resumable RUN session: prev_id=%s",
                new_session_id,
            )
            return session

        return None


def create_resume_strategy(
    mode: SessionMode, repository: SessionRepository
) -> SessionResumeStrategy:
    """Factory function to create the appropriate resume strategy.

    Args:
        mode: The session mode
        repository: The session repository

    Returns:
        The appropriate resume strategy for the mode
    """
    if mode == SessionMode.EDIT:
        return EditModeResumeStrategy(repository)
    else:
        return RunModeResumeStrategy(repository)
