"""Unit tests for ``google.colab._bridge``."""

from __future__ import annotations

import sys

import pytest

from google.colab import _bridge


def test_request_auth_round_trip(install_fake_stdin):
    fake = install_fake_stdin()

    response = _bridge.request_auth(
        ["https://www.googleapis.com/auth/drive"],
        request_id="rid-test-1",
    )

    assert len(fake.requests) == 1
    sent = fake.requests[0]
    assert sent == {
        "protocol_version": 1,
        "request_id": "rid-test-1",
        "provider": "google",
        "scopes": ["https://www.googleapis.com/auth/drive"],
        "include_granted_scopes": True,
        "hosted_domain": None,
    }
    assert response["access_token"] == "FAKE_TEST_TOKEN"
    assert response["token_type"] == "Bearer"
    assert response["expires_at"] == 9_999_999_999
    assert "_raw" in response


def test_request_auth_raises_when_unavailable(monkeypatch):
    class NoAuth:
        # No ``_request_auth`` attribute.
        pass

    monkeypatch.setattr(sys, "stdin", NoAuth())
    with pytest.raises(_bridge.AuthBridgeUnavailableError):
        _bridge.request_auth(["scope1"])


def test_request_auth_propagates_frontend_error(install_fake_stdin):
    def responder(req):
        return {
            "protocol_version": 1,
            "request_id": req["request_id"],
            "status": "error",
            "error_code": "user_cancelled",
            "error_message": "user closed popup",
        }

    install_fake_stdin(responder)

    with pytest.raises(_bridge.AuthRequestRejectedError) as exc_info:
        _bridge.request_auth(["scope1"])
    assert exc_info.value.code == "user_cancelled"
    assert "user closed popup" in exc_info.value.message


def test_request_auth_rejects_request_id_mismatch(install_fake_stdin):
    def responder(req):
        return {
            "protocol_version": 1,
            "request_id": "wrong-id",
            "status": "ok",
            "access_token": "x",
            "expires_at": 1,
            "scope": "",
            "token_type": "Bearer",
        }

    install_fake_stdin(responder)
    with pytest.raises(_bridge.AuthResponseValidationError):
        _bridge.request_auth(["scope1"], request_id="rid-mismatch")


def test_request_auth_rejects_protocol_version(install_fake_stdin):
    def responder(req):
        return {
            "protocol_version": 999,
            "request_id": req["request_id"],
            "status": "ok",
            "access_token": "x",
        }

    install_fake_stdin(responder)
    with pytest.raises(_bridge.AuthResponseValidationError):
        _bridge.request_auth(["s"])


def test_request_auth_rejects_missing_token(install_fake_stdin):
    def responder(req):
        return {
            "protocol_version": 1,
            "request_id": req["request_id"],
            "status": "ok",
            "expires_at": 1,
        }

    install_fake_stdin(responder)
    with pytest.raises(_bridge.AuthResponseValidationError):
        _bridge.request_auth(["s"])


def test_request_auth_accepts_expires_in_fallback(install_fake_stdin):
    def responder(req):
        return {
            "protocol_version": 1,
            "request_id": req["request_id"],
            "status": "ok",
            "access_token": "ya29.xx",
            "expires_in": 3600,
            "scope": "drive",
            "token_type": "Bearer",
        }

    install_fake_stdin(responder)
    response = _bridge.request_auth(["s"])
    # expires_at is computed from now + 3600; tolerate clock variance.
    import time

    assert abs(response["expires_at"] - (time.time() + 3600)) < 5


def test_request_auth_rejects_non_json(install_fake_stdin):
    class BadStdin:
        def _request_auth(self, payload):
            return "not json {{{"

    import sys

    sys.stdin = BadStdin()
    with pytest.raises(_bridge.AuthResponseValidationError):
        _bridge.request_auth(["s"])
