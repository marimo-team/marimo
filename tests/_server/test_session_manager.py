import asyncio
from unittest.mock import MagicMock, Mock

import pytest

from marimo._config.manager import UserConfigManager
from marimo._server.file_manager import AppFileManager
from marimo._server.file_router import AppFileRouter
from marimo._server.model import ConnectionState, SessionConsumer, SessionMode
from marimo._server.sessions import LspServer, Session, SessionManager


@pytest.fixture
def mock_session_consumer():
    return Mock(spec=SessionConsumer)


@pytest.fixture
def mock_session():
    session = Mock(spec=Session)
    session.connection_state.return_value = ConnectionState.OPEN
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
        user_config_manager=UserConfigManager(),
    )


def test_start_lsp_server(session_manager: SessionManager):
    asyncio.get_event_loop().run_until_complete(
        session_manager.start_lsp_server()
    )
    session_manager.lsp_server.start.assert_called_once()


def test_create_session_new(
    session_manager: SessionManager, mock_session_consumer: SessionConsumer
):
    session_id = "test_session_id"
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


def test_create_session_absolute_url(
    session_manager: SessionManager,
    mock_session_consumer: SessionConsumer,
    temp_marimo_file: str,
):
    session_id = "test_session_id"
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
    session_manager: SessionManager, mock_session: Session
):
    session_id = "test_session_id"
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
):
    session_id = "test_session_id"
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


def test_close_session(session_manager: SessionManager, mock_session: Session):
    session_id = "test_session_id"
    session_manager.sessions[session_id] = mock_session
    session_manager.close_session(session_id)
    assert session_id not in session_manager.sessions
    mock_session.close.assert_called_once()


def test_any_clients_connected_new_file(
    session_manager: SessionManager, mock_session: Session
):
    session_id = "test_session_id"
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
):
    session_id = "test_session_id"
    session_manager.sessions[session_id] = mock_session
    mock_session.app_file_manager = AppFileManager(filename=temp_marimo_file)
    assert (
        session_manager.any_clients_connected(AppFileRouter.NEW_FILE) is False
    )
    assert session_manager.any_clients_connected(temp_marimo_file) is True
    assert session_manager.any_clients_connected("different_file.py") is False


def test_close_all_sessions(
    session_manager: SessionManager, mock_session: Session
):
    session_manager.sessions = {
        "session1": mock_session,
        "session2": mock_session,
    }
    session_manager.close_all_sessions()
    assert len(session_manager.sessions) == 0
    assert mock_session.close.call_count == 2


def test_shutdown(session_manager: SessionManager, mock_session: Session):
    session_manager.sessions = {
        "session1": mock_session,
        "session2": mock_session,
    }

    session_manager.shutdown()
    session_manager.lsp_server.stop.assert_called_once()
    assert len(session_manager.sessions) == 0
    assert mock_session.close.call_count == 2
