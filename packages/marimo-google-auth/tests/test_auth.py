"""Unit tests for ``google.colab.auth.authenticate_user``."""

from __future__ import annotations

import pytest


def test_authenticate_user_round_trip(install_fake_stdin, adc_paths, clear_auth_cache):
    from google.colab import _adc
    from google.colab import auth as colab_auth

    fake = install_fake_stdin()
    creds = colab_auth.authenticate_user(_marimo_scopes=["drive", "sheets"])

    # Bridge was called once with the requested scopes.
    assert len(fake.requests) == 1
    assert fake.requests[0]["scopes"] == ["drive", "sheets"]

    # Returned credentials carry the access token.
    assert creds.token == "FAKE_TEST_TOKEN"
    # And the expiry was populated.
    assert creds.expiry is not None

    # ADC + sidecar were written.
    assert _adc.default_adc_path().exists()
    assert _adc.read_sidecar_scopes() == ["drive", "sheets"]


def test_authenticate_user_uses_default_scopes(
    install_fake_stdin, adc_paths, clear_auth_cache
):
    from google.colab import auth as colab_auth

    fake = install_fake_stdin()
    colab_auth.authenticate_user()

    sent = fake.requests[0]
    assert "https://www.googleapis.com/auth/drive" in sent["scopes"]
    assert "https://www.googleapis.com/auth/userinfo.email" in sent["scopes"]


def test_authenticate_user_caches_token(
    install_fake_stdin, adc_paths, clear_auth_cache
):
    from google.colab import auth as colab_auth

    fake = install_fake_stdin()
    colab_auth.authenticate_user(_marimo_scopes=["drive"])
    colab_auth.authenticate_user(_marimo_scopes=["drive"])

    # Only one round-trip — second call hit the cache.
    assert len(fake.requests) == 1


def test_authenticate_user_force_bypasses_cache(
    install_fake_stdin, adc_paths, clear_auth_cache
):
    from google.colab import auth as colab_auth

    fake = install_fake_stdin()
    colab_auth.authenticate_user(_marimo_scopes=["drive"])
    colab_auth.authenticate_user(_marimo_scopes=["drive"], _force=True)

    assert len(fake.requests) == 2


def test_authenticate_user_re_prompts_on_scope_widening(
    install_fake_stdin, adc_paths, clear_auth_cache
):
    from google.colab import auth as colab_auth

    fake = install_fake_stdin()
    colab_auth.authenticate_user(_marimo_scopes=["drive"])
    colab_auth.authenticate_user(_marimo_scopes=["drive", "sheets"])

    # Second call had a new scope so cache was invalidated.
    assert len(fake.requests) == 2
    assert fake.requests[1]["scopes"] == ["drive", "sheets"]


def test_authenticate_user_re_prompts_on_expired_token(
    install_fake_stdin, adc_paths, clear_auth_cache
):
    """If the cached token expired, ``authenticate_user`` should re-prompt."""
    from google.colab import auth as colab_auth

    seq = iter(
        [
            # First call: about-to-expire token.
            {
                "protocol_version": 1,
                "status": "ok",
                "access_token": "expiring",
                "expires_at": 1,  # 1970 — definitely past.
                "scope": "drive",
                "token_type": "Bearer",
            },
            # Second call: fresh token.
            {
                "protocol_version": 1,
                "status": "ok",
                "access_token": "fresh",
                "expires_at": 9_999_999_999,
                "scope": "drive",
                "token_type": "Bearer",
            },
        ]
    )

    def responder(req):
        body = next(seq)
        body["request_id"] = req["request_id"]
        return body

    fake = install_fake_stdin(responder)
    creds_a = colab_auth.authenticate_user(_marimo_scopes=["drive"])
    creds_b = colab_auth.authenticate_user(_marimo_scopes=["drive"])

    assert len(fake.requests) == 2
    assert creds_a.token == "expiring"
    assert creds_b.token == "fresh"


def test_authenticate_user_raises_auth_error_on_bridge_failure(
    install_fake_stdin, adc_paths, clear_auth_cache
):
    from google.colab import auth as colab_auth

    def responder(req):
        return {
            "protocol_version": 1,
            "request_id": req["request_id"],
            "status": "error",
            "error_code": "user_cancelled",
            "error_message": "no",
        }

    install_fake_stdin(responder)

    with pytest.raises(colab_auth.AuthError):
        colab_auth.authenticate_user(_marimo_scopes=["drive"])
