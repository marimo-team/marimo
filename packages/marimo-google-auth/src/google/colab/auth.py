"""Public ``google.colab.auth`` surface for marimo notebooks.

Drop-in shim that satisfies the contract real Google Colab provides:

.. code:: python

    from google.colab import auth
    auth.authenticate_user()

After ``authenticate_user()`` returns, the caller receives a
``google.oauth2.credentials.Credentials`` object with a valid access
token. This is what the ``pydata_google_auth`` patch hands directly to
libraries like ``gdrive_fsspec``.

We also write ADC/sidecar files. ``google.auth.default()`` can use the
ADC file until the access token expires, but cannot refresh through
google-auth because the refresh token is intentionally fake.

Underneath, the call funnels through marimo's stdin auth-request RPC
(see ``_bridge.py``) into the frontend, which drives the actual OAuth
flow (browser popup / parent-frame token service / Clerk-backed
endpoint — that part is owned by the deployer).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from google.colab import _adc, _bridge

if TYPE_CHECKING:
    from collections.abc import Sequence

LOGGER = logging.getLogger(__name__)

# Default scope bundle for the no-argument ``authenticate_user()`` call,
# matching real Colab's broad pre-grant.
# Can strongly type?
_DEFAULT_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/devstorage.full_control",
)

# Refresh threshold: re-prompt the user if the cached token is within
# this many seconds of expiry. Matches the OAuth refresh skew gcloud
# uses; keeps clock-skew-safe without being prompt-spammy.
_REFRESH_SKEW_S = 60

_lock = threading.Lock()
_cached: dict[str, Any] | None = None


class AuthError(RuntimeError):
    """Public error class re-exported for users who want to except on it."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


def authenticate_user(
    clear_output: bool = True,  # noqa: ARG001 — Colab API compat
    *,
    _marimo_scopes: Sequence[str] | None = None,
    _force: bool = False,
) -> Any:
    """Authenticate the current user and return credentials.

    Args:
      clear_output: Accepted for Colab API parity; ignored. Real Colab
        uses it to clear IPython output after the popup closes.
      _marimo_scopes: Internal. Subset of OAuth scopes to request. Used
        by the ``pydata_google_auth`` patch to ask for exactly what the
        caller library needs. If ``None``, uses the default bundle.
      _force: Internal. Skip the in-process cache and force a fresh
        round-trip even if the cached token is still valid.

    Returns:
      A ``google.oauth2.credentials.Credentials`` object with the
      bearer token populated. Real Colab returns ``None``; we return
      the credentials so the pydata patch can hand them straight to
      callers without a second ADC round-trip.

    Raises:
      AuthError: On bridge / response / I/O failures.
    """
    scopes = tuple(_marimo_scopes) if _marimo_scopes is not None else _DEFAULT_SCOPES

    with _lock:
        cached = _cached
        if not _force and cached is not None and _cache_valid_for(cached, scopes):
            LOGGER.debug(
                "authenticate_user: reusing cached token (expires_at=%s)",
                cached["expires_at"],
            )
            return _credentials_from_cache(cached)

        try:
            response = _bridge.request_auth(scopes)
        except _bridge.AuthRequestRejectedError as e:
            raise AuthError(str(e), code=e.code) from e
        except _bridge.AuthBridgeError as e:
            raise AuthError(str(e)) from e

        try:
            _adc.write_adc(
                access_token=response["access_token"],
                expires_at=response["expires_at"],
                scopes=scopes,
            )
        except OSError as e:
            # Don't fail the call — google.auth.default() will fail
            # later, but if the user only needs the returned Credentials
            # object directly (via the pydata patch), they're fine.
            LOGGER.warning("marimo-google-auth: failed to write ADC: %s", e)

        cached = {
            "access_token": response["access_token"],
            "expires_at": response["expires_at"],
            "scope": response["scope"],
            "scopes": list(scopes),
            "token_type": response.get("token_type", "Bearer"),
        }
        _set_cache(cached)
        return _credentials_from_cache(cached)


def _cache_valid_for(cache: dict[str, Any], requested_scopes: Sequence[str]) -> bool:
    expires_at = cache.get("expires_at") or 0
    if expires_at - time.time() < _REFRESH_SKEW_S:
        return False
    granted = set(cache.get("scopes") or [])
    return set(requested_scopes).issubset(granted)


def _credentials_from_cache(cache: dict[str, Any]) -> Any:
    """Build a ``google.oauth2.credentials.Credentials`` from the cache.

    Importing google-auth lazily so that ``import google.colab.auth``
    stays cheap even if a downstream library only needs the patch
    side-effect.
    """
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=cache["access_token"],
        scopes=list(cache.get("scopes") or []),
    )
    # google-auth normally derives expiry from the OAuth refresh
    # response. Inject it directly so libraries that check
    # ``credentials.expired`` make the right decision.
    try:
        # ``expiry`` must be a naive UTC ``datetime`` per google-auth.
        from datetime import datetime, timezone

        creds.expiry = datetime.fromtimestamp(
            cache["expires_at"], tz=timezone.utc
        ).replace(tzinfo=None)
    except Exception:
        # Best-effort. A missing ``expiry`` just means clients won't
        # attempt auto-refresh through google-auth, which is the
        # intended behavior — refresh runs through the stdin bridge.
        pass
    return creds


def _set_cache(cache: dict[str, Any]) -> None:
    global _cached
    _cached = cache


def _clear_cache() -> None:
    """Test-only helper to reset the in-process token cache."""
    global _cached
    with _lock:
        _cached = None
