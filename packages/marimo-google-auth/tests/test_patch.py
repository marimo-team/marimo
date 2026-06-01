"""Unit tests for ``google.colab._patch``."""

from __future__ import annotations

import pytest

# Skip the whole file if pydata-google-auth isn't installed.
pytest.importorskip("pydata_google_auth")


def test_install_patch_is_idempotent(uninstall_patch):
    import pydata_google_auth.auth as pga

    from google.colab import _patch

    assert _patch.install_pydata_patch() is True
    assert _patch.is_installed()
    patched = pga.get_colab_default_credentials

    assert _patch.install_pydata_patch() is True
    assert pga.get_colab_default_credentials is patched


def test_uninstall_restores_original(uninstall_patch):
    import pydata_google_auth.auth as pga

    from google.colab import _patch

    original = pga.get_colab_default_credentials
    _patch.install_pydata_patch()
    assert pga.get_colab_default_credentials is not original

    _patch.uninstall_pydata_patch()
    assert pga.get_colab_default_credentials is original
    assert not _patch.is_installed()


def test_patched_function_calls_bridge(
    install_fake_stdin, adc_paths, clear_auth_cache, uninstall_patch
):
    import pydata_google_auth.auth as pga

    from google.colab import _patch

    fake = install_fake_stdin()
    _patch.install_pydata_patch()

    creds, project = pga.get_colab_default_credentials(
        ["https://www.googleapis.com/auth/drive"]
    )

    assert project is None
    assert creds is not None
    assert creds.token == "FAKE_TEST_TOKEN"
    assert len(fake.requests) == 1
    assert fake.requests[0]["scopes"] == ["https://www.googleapis.com/auth/drive"]


def test_patched_function_swallows_errors(
    install_fake_stdin, adc_paths, clear_auth_cache, uninstall_patch
):
    """Mirror pydata's tolerance: on failure, return ``(None, None)``."""
    import pydata_google_auth.auth as pga

    from google.colab import _patch

    def responder(req):
        return {
            "protocol_version": 1,
            "request_id": req["request_id"],
            "status": "error",
            "error_code": "user_cancelled",
            "error_message": "no",
        }

    install_fake_stdin(responder)
    _patch.install_pydata_patch()

    creds, project = pga.get_colab_default_credentials(["drive"])
    assert creds is None
    assert project is None


def test_patched_function_falls_back_when_parent_unavailable(
    install_fake_stdin, adc_paths, clear_auth_cache, uninstall_patch
):
    """Top-level/self-hosted marimo should fall through to pydata's local flow."""
    import pydata_google_auth.auth as pga

    from google.colab import _patch

    def responder(req):
        return {
            "protocol_version": 1,
            "request_id": req["request_id"],
            "status": "error",
            "error_code": "parent_unavailable",
            "error_message": "no parent bridge",
        }

    install_fake_stdin(responder)
    _patch.install_pydata_patch()

    creds, project = pga.get_colab_default_credentials(["drive"])
    assert creds is None
    assert project is None
