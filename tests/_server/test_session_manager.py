import asyncio
from unittest.mock import MagicMock, Mock

import pytest

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
        filename=None,
        mode=SessionMode.EDIT,
        development_mode=False,
        quiet=False,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
    )


def test_start_lsp_server(session_manager: SessionManager):
    asyncio.get_event_loop().run_until_complete(
        session_manager.start_lsp_server()
    )
    session_manager.lsp_server.start.assert_called_once()


def test_create_session(
    session_manager: SessionManager, mock_session_consumer: SessionConsumer
):
    session_id = "test_session_id"
    session = session_manager.create_session(session_id, mock_session_consumer)
    assert session_id in session_manager.sessions
    assert session_manager.get_session(session_id) is session
    # Close ourselves to finish the test
    session.close()


def test_rename(session_manager: SessionManager):
    new_filename = "new_test.py"
    session_manager.rename(new_filename)
    assert session_manager.filename == new_filename


def test_maybe_resume_session(
    session_manager: SessionManager, mock_session: Session
):
    session_id = "test_session_id"
    mock_session.connection_state.return_value = ConnectionState.ORPHANED
    session_manager.sessions[session_id] = mock_session
    resumed_session = session_manager.maybe_resume_session(session_id)
    assert resumed_session is mock_session


def test_close_session(session_manager: SessionManager, mock_session: Session):
    session_id = "test_session_id"
    session_manager.sessions[session_id] = mock_session
    session_manager.close_session(session_id)
    assert session_id not in session_manager.sessions
    mock_session.close.assert_called_once()


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
