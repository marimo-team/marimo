from __future__ import annotations

from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.authentication import (
    SimpleUser,
)
from starlette.middleware import Middleware
from starlette.middleware.authentication import (
    AuthenticationMiddleware,
)
from starlette.middleware.sessions import SessionMiddleware
from starlette.testclient import TestClient

from marimo._server.api.endpoints.login import router as auth_router
from marimo._server.api.middleware import AuthBackend
from marimo._server.router import APIRouter
from marimo._server.tokens import AuthToken
from tests._server.mocks import get_starlette_server_state_init

AUTH_TOKEN = AuthToken("test_password")


def create_app(base_url: str = "") -> Starlette:
    router = APIRouter(prefix=base_url)
    router.include_router(auth_router)
    app = Starlette(
        routes=router.routes,
        middleware=[
            Middleware(
                SessionMiddleware,
                secret_key="test_secret",
                session_cookie="test_session",
            ),
            Middleware(
                AuthenticationMiddleware,
                backend=AuthBackend(should_authenticate=True),
            ),
        ],
    )
    get_starlette_server_state_init(base_url=base_url).apply(app.state)
    app.state.session_manager._token_manager.auth_token = AUTH_TOKEN
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(base_url=""), follow_redirects=False)


def test_login_page_returns_html(client: TestClient):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Access Token / Password" in response.text


def test_login_submit_with_valid_password(client: TestClient):
    response = client.post("/login", data={"password": str(AUTH_TOKEN)})
    assert response.status_code == 302, response.text
    assert response.headers["location"] == "/"


def test_login_submit_with_invalid_password(client: TestClient):
    response = client.post("/login", data={"password": "wrong_password"})
    assert response.status_code == 200
    assert "Invalid password" in response.text


def test_login_submit_with_empty_password(client: TestClient):
    response = client.post("/login", data={"password": ""})
    assert response.status_code == 200
    assert "Password is required" in response.text


def test_login_submit_with_authenticated_user(client: TestClient):
    with patch(
        "starlette.requests.Request", return_value=True
    ) as mock_request:
        mock_request.user = SimpleUser("test_user")
        response = client.post("/login", data={"password": str(AUTH_TOKEN)})
        assert response.status_code == 302, response.text
        assert response.headers["location"] == "/"


def test_login_submit_with_next_url(client: TestClient):
    response = client.post(
        "/login?next=/dashboard",
        data={"password": str(AUTH_TOKEN)},
    )
    assert response.status_code == 302, response.text
    assert response.headers["location"] == "/dashboard"


def test_login_page_with_base_url():
    app = create_app(base_url="/app")
    client = TestClient(app, follow_redirects=False)
    response = client.get("/app/login")
    assert response.status_code == 200, response.text
    assert "Access Token / Password" in response.text
    assert 'action="/app/auth/login"' in response.text


def test_login_submit_with_base_url():
    app = create_app(base_url="/app")
    client = TestClient(app, follow_redirects=False)
    response = client.post("/app/login", data={"password": str(AUTH_TOKEN)})
    assert response.status_code == 302, response.text
    assert response.headers["location"] == "/app/"


def test_login_submit_with_base_url_trailing_slash():
    app = create_app(base_url="/app/")
    client = TestClient(app, follow_redirects=False)
    response = client.post("/app/login", data={"password": str(AUTH_TOKEN)})
    assert response.status_code == 302, response.text
    assert response.headers["location"] == "/app/"


def test_login_submit_with_next_url_and_base_url():
    app = create_app(base_url="/app")
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/app/login?next=/app/dashboard",
        data={"password": str(AUTH_TOKEN)},
    )
    assert response.status_code == 302, response.text
    assert response.headers["location"] == "/app/dashboard"


def test_login_page_security_headers(client: TestClient):
    response = client.get("/login")
    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_login_submit_with_external_redirect(client: TestClient):
    response = client.post(
        "/login?next=https://evil.com",
        data={"password": str(AUTH_TOKEN)},
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_login_submit_with_protocol_relative_redirect(client: TestClient):
    """Protocol-relative URLs (//evil.com) must not bypass open redirect protection."""
    response = client.post(
        "/login?next=//evil.com",
        data={"password": str(AUTH_TOKEN)},
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_login_submit_with_malformed_data(client: TestClient):
    response = client.post(
        "/login",
        content=b"invalid=form=data",  # type: ignore
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    assert "Password is required" in response.text


def test_login_page_method_not_allowed(client: TestClient):
    response = client.put("/login")
    assert response.status_code == 405


def test_login_submit_multiple_invalid_attempts(client: TestClient):
    """Test that multiple failed login attempts still show the login form correctly."""
    # First invalid attempt
    response = client.post("/login", data={"password": "wrong_password"})
    assert response.status_code == 200
    assert "Invalid password" in response.text
    assert 'action="/auth/login"' in response.text

    # Second invalid attempt - this should still work
    response = client.post("/login", data={"password": "wrong_password2"})
    assert response.status_code == 200
    assert "Invalid password" in response.text
    assert 'action="/auth/login"' in response.text

    # Third attempt with correct password should succeed
    response = client.post("/login", data={"password": str(AUTH_TOKEN)})
    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_login_submit_invalid_password_with_base_url():
    """Test that invalid login with base_url shows correct form action."""
    app = create_app(base_url="/app")
    client = TestClient(app, follow_redirects=False)

    # First invalid attempt
    response = client.post("/app/login", data={"password": "wrong_password"})
    assert response.status_code == 200
    assert "Invalid password" in response.text
    assert 'action="/app/auth/login"' in response.text

    # Second invalid attempt
    response = client.post("/app/login", data={"password": "wrong_password2"})
    assert response.status_code == 200
    assert "Invalid password" in response.text
    assert 'action="/app/auth/login"' in response.text


def test_auth_token_returns_token_when_authenticated(client: TestClient):
    """Authenticated user gets the auth token."""
    # First authenticate via login
    client.post("/login", data={"password": str(AUTH_TOKEN)})
    response = client.get("/token")
    assert response.status_code == 200
    data = response.json()
    assert data["token"] == str(AUTH_TOKEN)
    assert response.headers["Cache-Control"] == "no-store"


def test_auth_token_unauthenticated_returns_403(client: TestClient):
    """Unauthenticated request to /token is rejected."""
    response = client.get("/token")
    assert response.status_code == 403


def test_auth_token_returns_null_when_auth_disabled():
    """When auth is disabled, /token returns null."""
    app = create_app()
    app.state.enable_auth = False
    # Auth middleware still present but we authenticate first
    test_client = TestClient(app, follow_redirects=False)
    test_client.post("/login", data={"password": str(AUTH_TOKEN)})
    response = test_client.get("/token")
    assert response.status_code == 200
    assert response.json()["token"] is None


def test_bearer_auth_valid_token(client: TestClient):
    """Bearer token auth grants access."""
    response = client.get(
        "/token",
        headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
    )
    assert response.status_code == 200
    assert response.json()["token"] == str(AUTH_TOKEN)


def test_bearer_auth_invalid_token(client: TestClient):
    """Bearer token with wrong value is rejected."""
    response = client.get(
        "/token",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 403
