from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock

import pytest

from marimo._config.manager import get_default_config_manager
from marimo._server.file_manager import AppFileManager
from marimo._server.file_router import AppFileRouter
from marimo._server.model import ConnectionState, SessionConsumer, SessionMode
from marimo._server.sessions import (
    KernelManager,
    LspServer,
    Session,
    SessionManager,
)
from marimo._server.tokens import AuthToken, SkewProtectionToken
from marimo._types.ids import SessionId

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_session_consumer():
    mock = Mock(spec=SessionConsumer)
    mock.consumer_id = "test_consumer_id"
    return mock


@pytest.fixture
def mock_session():
    session = Mock(spec=Session)
    session.connection_state.return_value = ConnectionState.OPEN
    session.kernel_manager = Mock(spec=KernelManager)
    session.kernel_manager.kernel_task = None
    return session


@pytest.fixture
def session_manager():
    return SessionManager(
        file_router=AppFileRouter.new_file(),
        mode=SessionMode.EDIT,
        development_mode=False,
        quiet=False,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )


session_id = SessionId("test_session_id")


async def test_start_lsp_server(session_manager: SessionManager) -> None:
    await session_manager.start_lsp_server()
    session_manager.lsp_server.start.assert_called_once()


async def test_create_session_new(
    session_manager: SessionManager, mock_session_consumer: SessionConsumer
) -> None:
    session = session_manager.create_session(
        session_id,
        mock_session_consumer,
        query_params={},
        file_key=AppFileRouter.NEW_FILE,
    )
    assert session_id in session_manager.sessions
    assert session_manager.get_session(session_id) is session
    # Close ourselves to finish the test
    session.close()


async def test_create_session_absolute_url(
    session_manager: SessionManager,
    mock_session_consumer: SessionConsumer,
    temp_marimo_file: str,
) -> None:
    session = session_manager.create_session(
        session_id,
        mock_session_consumer,
        query_params={},
        file_key=temp_marimo_file,
    )
    assert session_id in session_manager.sessions
    assert session_manager.get_session(session_id) is session
    # Close ourselves to finish the test
    session.close()


def test_maybe_resume_session_for_new_file(
    session_manager: SessionManager,
    mock_session: Session,
) -> None:
    mock_session.connection_state.return_value = ConnectionState.ORPHANED
    mock_session.app_file_manager = AppFileManager(filename=None)
    session_manager.sessions[session_id] = mock_session

    # Resume the same session_id with a new file -> doesn't match
    resumed_session = session_manager.maybe_resume_session(
        session_id, AppFileRouter.NEW_FILE
    )
    assert resumed_session is None

    # Resume the same session_id with a different file -> doesn't match
    # This is technically a bad state and should be unreachable
    resumed_session = session_manager.maybe_resume_session(
        session_id, "different_file.py"
    )
    assert resumed_session is None

    # Resume with a different session_id -> doesn't match
    resumed_session = session_manager.maybe_resume_session(
        "different_session_id", AppFileRouter.NEW_FILE
    )
    assert resumed_session is None


def test_maybe_resume_session_for_existing_file(
    session_manager: SessionManager,
    mock_session: Session,
    temp_marimo_file: str,
) -> None:
    mock_session.connection_state.return_value = ConnectionState.ORPHANED
    mock_session.app_file_manager = AppFileManager(filename=temp_marimo_file)
    session_manager.sessions[session_id] = mock_session

    # Resume the same session_id with the same file -> matches
    resumed_session = session_manager.maybe_resume_session(
        session_id, temp_marimo_file
    )
    assert resumed_session is mock_session

    # Resume the same session_id with a different file -> doesn't match
    # This is technically a bad state and should be unreachable
    resumed_session = session_manager.maybe_resume_session(
        session_id, "different_file.py"
    )
    assert resumed_session is None

    # Resume with a different session_id -> matches
    resumed_session = session_manager.maybe_resume_session(
        "different_session_id", temp_marimo_file
    )
    assert resumed_session is mock_session


def test_close_session(
    session_manager: SessionManager, mock_session: Session
) -> None:
    mock_session.app_file_manager = AppFileManager(filename=None)
    session_manager.sessions[session_id] = mock_session
    assert session_manager.close_session(session_id)
    assert session_id not in session_manager.sessions
    mock_session.close.assert_called_once()


def test_any_clients_connected_new_file(
    session_manager: SessionManager, mock_session: Session
) -> None:
    session_manager.sessions[session_id] = mock_session
    mock_session.app_file_manager = AppFileManager(filename=None)
    assert (
        session_manager.any_clients_connected(AppFileRouter.NEW_FILE) is False
    )
    assert session_manager.any_clients_connected("different_file.py") is False


def test_any_clients_connected_existing_file(
    session_manager: SessionManager,
    mock_session: Session,
    temp_marimo_file: str,
) -> None:
    session_manager.sessions[session_id] = mock_session
    mock_session.app_file_manager = AppFileManager(filename=temp_marimo_file)
    assert (
        session_manager.any_clients_connected(AppFileRouter.NEW_FILE) is False
    )
    assert session_manager.any_clients_connected(temp_marimo_file) is True
    assert session_manager.any_clients_connected("different_file.py") is False


def test_close_all_sessions(
    session_manager: SessionManager, mock_session: Session
) -> None:
    session_manager.sessions = {
        "session1": mock_session,
        "session2": mock_session,
    }
    session_manager.close_all_sessions()
    assert len(session_manager.sessions) == 0
    assert mock_session.close.call_count == 2


def test_shutdown(
    session_manager: SessionManager, mock_session: Session
) -> None:
    session_manager.sessions = {
        "session1": mock_session,
        "session2": mock_session,
    }

    session_manager.shutdown()
    session_manager.lsp_server.stop.assert_called_once()
    assert len(session_manager.sessions) == 0
    assert mock_session.close.call_count == 2


async def test_create_session_with_script_config_overrides(
    session_manager: SessionManager,
    mock_session_consumer: SessionConsumer,
    tmp_path: Path,
) -> None:
    tmp_file = tmp_path / "test.py"
    tmp_file.write_text(
        dedent(
            """
        # /// script
        # [tool.marimo.formatting]
        # line_length = 999
        # ///
        """
        )
    )

    session = session_manager.create_session(
        session_id,
        mock_session_consumer,
        query_params={},
        file_key=str(tmp_path / "test.py"),
    )
    assert session_id in session_manager.sessions
    assert session_manager.get_session(session_id) is session

    # Verify that the session's config is affected by the script config
    assert (
        session.config_manager.get_config()["formatting"]["line_length"] == 999
    )

    # Verify that the session manager's config is not affected by the script config
    assert (
        session_manager._config_manager.get_config()["formatting"][
            "line_length"
        ]
        != 999
    )

    session.close()


def test_session_manager_auth_token_edit_mode_with_provided_token():
    """Test that provided auth token is used in EDIT mode"""
    provided_token = AuthToken("custom-edit-token")
    session_manager = SessionManager(
        file_router=AppFileRouter.new_file(),
        mode=SessionMode.EDIT,
        development_mode=False,
        quiet=False,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=provided_token,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )

    assert session_manager.auth_token is provided_token
    assert str(session_manager.auth_token) == "custom-edit-token"
    assert session_manager.skew_protection_token is not None


def test_session_manager_auth_token_edit_mode_without_provided_token():
    """Test that random auth token is generated in EDIT mode when none provided"""
    session_manager = SessionManager(
        file_router=AppFileRouter.new_file(),
        mode=SessionMode.EDIT,
        development_mode=False,
        quiet=False,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )

    # Should generate a random token (we can't predict the value, but it should exist)
    assert session_manager.auth_token is not None
    assert str(session_manager.auth_token) != ""
    # Verify it's a random token by checking length (AuthToken.random() uses token_urlsafe(16))
    assert len(str(session_manager.auth_token)) > 10
    assert session_manager.skew_protection_token is not None


def test_session_manager_auth_token_run_mode_with_provided_token():
    """Test that provided auth token is used in RUN mode"""
    provided_token = AuthToken("custom-run-token")
    session_manager = SessionManager(
        file_router=AppFileRouter.new_file(),
        mode=SessionMode.RUN,
        development_mode=False,
        quiet=False,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=provided_token,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )

    assert session_manager.auth_token is provided_token
    assert str(session_manager.auth_token) == "custom-run-token"
    assert str(session_manager.skew_protection_token) == str(
        SkewProtectionToken.from_code("")
    )


def test_session_manager_auth_token_run_mode_without_provided_token(
    tmp_path: Path,
):
    """Test that code-based auth token is generated in RUN mode when none provided"""
    # Create a simple marimo file
    notebook_content = dedent(
        """\
        import marimo

        app = marimo.App()

        @app.cell
        def test_cell():
            "hello"
            return
        """
    )

    file_path = tmp_path / "test_notebook.py"
    file_path.write_text(notebook_content)

    session_manager = SessionManager(
        file_router=AppFileRouter.infer(str(file_path)),
        mode=SessionMode.RUN,
        development_mode=False,
        quiet=False,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )

    # Should generate a deterministic token based on code
    assert session_manager.auth_token is not None
    assert str(session_manager.auth_token) != ""
    assert str(session_manager.skew_protection_token) != ""

    # Create another session manager with the same code - should have same token
    session_manager2 = SessionManager(
        file_router=AppFileRouter.infer(str(file_path)),
        mode=SessionMode.RUN,
        development_mode=False,
        quiet=False,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )

    # Should have the same deterministic token
    assert str(session_manager.auth_token) == str(session_manager2.auth_token)
    assert str(session_manager.skew_protection_token) == str(
        session_manager2.skew_protection_token
    )
