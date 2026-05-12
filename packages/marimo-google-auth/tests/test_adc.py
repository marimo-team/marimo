"""Unit tests for ``google.colab._adc``."""

from __future__ import annotations

import json
import os
import stat

from google.colab import _adc


def test_write_adc_default_paths(adc_paths):
    """When using default paths (under tmp_path home), do not set the env var."""
    expected_adc = _adc.default_adc_path()
    expected_sidecar = _adc.default_sidecar_path()

    result = _adc.write_adc(
        access_token="ya29.fake",
        expires_at=1_700_000_000,
        scopes=["https://www.googleapis.com/auth/drive"],
    )

    assert result == expected_adc
    assert expected_adc.exists()
    assert expected_sidecar.exists()
    # env var should NOT be set when ADC is at the default path.
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ


def test_write_adc_contents(adc_paths):
    _adc.write_adc(
        access_token="ya29.contents",
        expires_at=42,
        scopes=["drive", "sheets"],
    )

    doc = json.loads(_adc.default_adc_path().read_text())
    assert doc["type"] == "authorized_user"
    assert doc["access_token"] == "ya29.contents"
    assert doc["expires_at"] == 42
    assert doc["scopes"] == ["drive", "sheets"]
    assert doc["issued_by"] == "marimo-google-auth"
    # google-auth requires these even when we don't use them.
    assert doc["refresh_token"]
    assert doc["client_id"]
    assert doc["client_secret"]


def test_write_adc_custom_path_sets_env(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr(_adc, "_ENV_VAR_PATHS_WE_OWN", set())
    custom_adc = tmp_path / "custom" / "adc.json"

    _adc.write_adc(
        access_token="t",
        expires_at=1,
        scopes=[],
        adc_path=custom_adc,
    )

    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(custom_adc)


def test_write_adc_default_path_clears_our_stale_env_var(tmp_path, monkeypatch):
    """Writing to the default path must clear a stale env var **we** set.

    Regression: the docstring promised this behavior but the original
    implementation never unset the variable, so a later default-path
    write would still be shadowed by the earlier custom-path env var.
    """
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr(_adc, "_ENV_VAR_PATHS_WE_OWN", set())
    custom_adc = tmp_path / "custom" / "adc.json"

    _adc.write_adc(
        access_token="t",
        expires_at=1,
        scopes=[],
        adc_path=custom_adc,
    )
    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(custom_adc)

    # Subsequent write to the default path: the previously-set env
    # var was ours, so we must remove it.
    _adc.write_adc(access_token="t", expires_at=1, scopes=[])
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ


def test_write_adc_default_path_preserves_user_env_var(tmp_path, monkeypatch):
    """A user-set env var (e.g. service account key) must not be clobbered.

    If ``GOOGLE_APPLICATION_CREDENTIALS`` points somewhere we never set
    it to, we have to assume it's intentional and leave it alone.
    """
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    user_path = tmp_path / "user-service-account.json"
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(user_path))
    monkeypatch.setattr(_adc, "_ENV_VAR_PATHS_WE_OWN", set())

    _adc.write_adc(access_token="t", expires_at=1, scopes=[])

    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(user_path)


def test_write_adc_file_mode_is_restrictive(adc_paths):
    _adc.write_adc(
        access_token="t",
        expires_at=1,
        scopes=[],
    )
    mode = stat.S_IMODE(_adc.default_adc_path().stat().st_mode)
    # Owner-only read/write.
    assert mode & 0o077 == 0, f"ADC file mode is too permissive: {oct(mode)}"


def test_sidecar_round_trip(adc_paths):
    _adc.write_adc(
        access_token="t",
        expires_at=1,
        scopes=["drive", "sheets"],
    )
    assert _adc.read_sidecar_scopes() == ["drive", "sheets"]


def test_missing_scopes(adc_paths):
    _adc.write_adc(
        access_token="t",
        expires_at=1,
        scopes=["drive"],
    )
    missing = _adc.missing_scopes(["drive", "sheets", "bigquery"])
    assert missing == ["sheets", "bigquery"]


def test_missing_scopes_no_sidecar(adc_paths):
    assert _adc.missing_scopes(["drive"]) == ["drive"]


def test_refresh_token_sentinel_is_unmistakable(adc_paths):
    """The stub refresh_token must be unambiguously non-real.

    Real Google refresh tokens start with ``1//`` and consist of
    base64url chars. If our sentinel accidentally matched that shape,
    a casual reader of an exfiltrated ADC file might waste cycles
    trying to use it. The sentinel exists precisely so that "this is
    a placeholder" is obvious on first glance.
    """
    _adc.write_adc(
        access_token="ya29.real-looking-access-token",
        expires_at=1,
        scopes=["drive"],
    )
    doc = json.loads(_adc.default_adc_path().read_text())

    refresh = doc["refresh_token"]
    # Shape: must not look like a real Google refresh token.
    assert not refresh.startswith("1//"), (
        "refresh_token sentinel must not match real Google refresh-token prefix"
    )
    # Must contain a clear "not real" marker.
    assert "NOT_A_REAL" in refresh, (
        "refresh_token sentinel must self-identify as a placeholder"
    )
    # Colons are forbidden in real refresh tokens; their presence is
    # a deliberate shape-mismatch tripwire.
    assert ":" in refresh, "refresh_token sentinel must contain colons"

    # Same property for the client_secret sentinel.
    secret = doc["client_secret"]
    assert "NOT_A_REAL" in secret, (
        "client_secret sentinel must self-identify as a placeholder"
    )

    # And the client_id stays parseable (ends in
    # `.apps.googleusercontent.com`) but is obviously a stub.
    client_id = doc["client_id"]
    assert client_id.endswith(".apps.googleusercontent.com"), (
        "client_id must keep Google's expected suffix so google-auth "
        "doesn't bail at parse time"
    )
    assert ".stub." in client_id, (
        "client_id sentinel must self-identify as a placeholder"
    )
