"""JSON envelope round-trip over marimo's stdin auth-request channel.

This is the low-level bridge module. Everything kernel-side that wants
an OAuth token from the frontend goes through ``request_auth``.

Wire protocol is documented in marimo's ``plan.md`` §5. In short:

- Kernel sends an ``application/x-marimo-auth-request`` stdin message
  carrying a JSON request envelope.
- Frontend renders provider-specific UI, drives the OAuth flow somehow,
  and POSTs a JSON response envelope back through ``/api/kernel/stdin``.
- ``sys.stdin._request_auth`` is the underscore-prefixed kernel API
  that performs this round-trip and blocks until a response arrives.

This module is internal. Public consumers should call
``google.colab.auth.authenticate_user`` instead.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Iterable, Mapping
from typing import Any

LOGGER = logging.getLogger(__name__)

PROTOCOL_VERSION = 1

# Default token lifetime when the frontend omits an explicit expiry. The
# OAuth 2.0 access-token contract is 1 hour; we mirror that and let
# ``_adc.write_adc`` propagate it.
DEFAULT_TOKEN_TTL_S = 3600


class AuthBridgeError(RuntimeError):
    """Base error for everything that can go wrong in the auth bridge."""


class AuthBridgeUnavailableError(AuthBridgeError):
    """``sys.stdin._request_auth`` isn't installed (not running inside marimo).

    Raised when the package is imported but no marimo kernel is wrapping
    ``sys.stdin``. This is *not* an OAuth failure — it means the host
    runtime is wrong.
    """


class AuthRequestRejectedError(AuthBridgeError):
    """The frontend returned a structured error envelope."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class AuthResponseValidationError(AuthBridgeError):
    """The frontend's JSON response failed schema validation."""


def _is_request_auth_available() -> bool:
    """Whether ``sys.stdin`` exposes the auth-request RPC.

    Tested with ``hasattr`` rather than module-path sniffing so we work
    against both the real marimo kernel and any future re-implementation
    that satisfies the same contract.
    """
    return hasattr(sys.stdin, "_request_auth") and callable(
        getattr(sys.stdin, "_request_auth", None)
    )


def _debug_log(msg: str) -> None:
    """Mirrors ``marimo._messaging.streams._auth_debug_log`` for tracing.

    Opt-in via the same ``MARIMO_AUTH_DEBUG_LOG`` env var and the same
    output file as the marimo kernel side. Tailing one file shows the
    full hop chain (kernel marimo -> kernel shim -> frontend -> back)
    in submission order, which is the only way to diagnose a stuck
    round-trip without a full kernel-debugger session.

    Falls back to ``LOGGER.debug`` when the env var is unset so the
    same call sites work for routine dev logging.

    Security contract — DO NOT relax:
      Callers must log **metadata only** (request IDs, byte counts,
      protocol versions). Never pass the raw payload, the access
      token, or any field of the response envelope into ``msg``.
      Compromising this property would turn an opt-in dev tracer
      into a token-exfiltration channel.
    """
    path = os.environ.get("MARIMO_AUTH_DEBUG_LOG")
    if not path:
        LOGGER.debug(msg)
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{time.time():.3f}] [bridge.py] {msg}\n")
    except Exception:
        # Tracer must never break the call.
        LOGGER.debug(msg)


def request_auth(
    scopes: Iterable[str],
    *,
    provider: str = "google",
    include_granted_scopes: bool = True,
    hosted_domain: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Send an auth request to the frontend; block for the response.

    Args:
      scopes: OAuth scopes requested. Order is preserved in the wire
        envelope.
      provider: Currently only ``"google"`` is supported by the
        frontend dispatch; reserved for future expansion (e.g. GitHub).
      include_granted_scopes: Hint to the frontend that it may surface
        an "add scope" flow rather than re-prompting from scratch.
      hosted_domain: Optional ``hd`` hint for Google's ``hd`` query
        parameter. ``None`` means any Google account is acceptable.
      request_id: Override for the envelope ``request_id``. Tests use
        this to keep snapshots stable; production should let it default.

    Returns:
      The validated success response dict, with at minimum keys
      ``access_token`` (str), ``expires_at`` (int, unix seconds),
      ``scope`` (str, space-separated), and ``token_type``.

    Raises:
      AuthBridgeUnavailableError: Not running inside marimo.
      AuthRequestRejectedError: Frontend returned ``status="error"``.
      AuthResponseValidationError: Frontend response was malformed or
        request_id mismatched.
    """
    if not _is_request_auth_available():
        raise AuthBridgeUnavailableError(
            "sys.stdin._request_auth is not installed. This package only "
            "works inside a marimo notebook kernel (>= the version that "
            "ships the auth-request stdin channel)."
        )

    scopes_list = list(scopes)
    rid = request_id or str(uuid.uuid4())
    envelope = {  # can we strongly type this?
        "protocol_version": PROTOCOL_VERSION,
        "request_id": rid,
        "provider": provider,
        "scopes": scopes_list,
        "include_granted_scopes": bool(include_granted_scopes),
        "hosted_domain": hosted_domain,
    }
    payload = json.dumps(envelope, separators=(",", ":"))
    _debug_log(
        "sending auth request "
        f"(request_id={rid}, scope_count={len(scopes_list)}, "
        f"payload_bytes={len(payload)})"
    )

    raw_response: str = sys.stdin._request_auth(payload)  # type: ignore[attr-defined]
    _debug_log(
        f"received auth response (request_id={rid}, response_bytes={len(raw_response)})"
    )

    response = _parse_response(raw_response, expected_request_id=rid)
    return response


# Is there a more built-in function to do this?
# Feels very tedious and fragile
def _parse_response(raw: str, *, expected_request_id: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AuthResponseValidationError(
            f"frontend response is not valid JSON: {e}"
        ) from e

    if not isinstance(parsed, Mapping):
        raise AuthResponseValidationError(
            f"frontend response is not a JSON object (got {type(parsed).__name__})"
        )

    if parsed.get("protocol_version") != PROTOCOL_VERSION:
        raise AuthResponseValidationError(
            f"protocol_version mismatch: expected {PROTOCOL_VERSION}, "
            f"got {parsed.get('protocol_version')!r}"
        )

    rid = parsed.get("request_id")
    if rid != expected_request_id:
        raise AuthResponseValidationError(
            f"request_id mismatch: expected {expected_request_id!r}, got {rid!r}"
        )

    status = parsed.get("status")
    if status == "error":
        code = str(parsed.get("error_code") or "unknown")
        message = str(parsed.get("error_message") or "")
        raise AuthRequestRejectedError(code=code, message=message)
    if status != "ok":
        raise AuthResponseValidationError(
            f"unknown status {status!r}; expected 'ok' or 'error'"
        )

    access_token = parsed.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise AuthResponseValidationError(
            "response is missing a non-empty 'access_token' string"
        )

    # Accept either expires_at (preferred, absolute unix seconds) or
    # expires_in (relative seconds, for compatibility with raw GIS
    # token-client output). Normalize to expires_at.
    expires_at_raw = parsed.get("expires_at")
    expires_in_raw = parsed.get("expires_in")
    if isinstance(expires_at_raw, (int, float)) and expires_at_raw > 0:
        expires_at = int(expires_at_raw)
    elif isinstance(expires_in_raw, (int, float)) and expires_in_raw > 0:
        expires_at = int(time.time() + expires_in_raw)
    else:
        # Frontend omitted expiry: use OAuth's standard 1h default.
        expires_at = int(time.time() + DEFAULT_TOKEN_TTL_S)

    scope = parsed.get("scope")
    if not isinstance(scope, str):
        scope = ""

    token_type = parsed.get("token_type") or "Bearer"

    # Strongly type?
    return {
        "access_token": access_token,
        "expires_at": expires_at,
        "scope": scope,
        "token_type": token_type,
        # Pass through anything else the frontend gave us. Useful for
        # future fields (e.g. client_id) without protocol churn.
        "_raw": dict(parsed),
    }
