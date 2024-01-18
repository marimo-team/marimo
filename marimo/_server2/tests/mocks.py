from marimo._server.model import SessionMode
from marimo._server2.api.deps import SessionManagerState

MOCK_MANAGER_STATE = SessionManagerState(
    server_token="test-server-token",
    filename="test_app.py",
    mode=SessionMode.RUN,
    app_config=None,
    quiet=False,
    development_mode=False,
)
