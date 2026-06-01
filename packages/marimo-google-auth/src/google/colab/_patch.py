"""Monkey-patch ``pydata_google_auth.auth.get_colab_default_credentials``.

Why this exists
---------------
``pydata-google-auth`` (which ``gdrive-fsspec``, ``pandas-gbq``, and
others use) already contains an escape hatch for Google Colab:

.. code:: python

    def get_colab_default_credentials(scopes):
        auth = try_colab_auth_import()   # `from google.colab import auth`
        if auth is None:
            return None, None
        try:
            auth.authenticate_user()
            return get_application_default_credentials(scopes=scopes)
        except Exception:
            return None, None

Two problems for us:

1. The vendor copy calls ``auth.authenticate_user()`` with **no
   scopes**. Real Colab's implementation pre-grants a broad scope set,
   so this works. Ours is per-request and needs to know what to ask for.
2. After ``authenticate_user()``, pydata would normally call
   ``get_application_default_credentials(scopes=scopes)``, which goes
   through ``google.auth.default()`` -> ADC file. Our ADC file works
   until access-token expiry, but cannot refresh through google-auth
   because the refresh token is intentionally fake.

Our patch fixes both:

- Forwards ``scopes`` directly into ``authenticate_user(_marimo_scopes=...)``
  so the user only sees a consent prompt for the scopes actually needed.
- Constructs a fresh ``google.oauth2.credentials.Credentials`` from the
  in-memory token cache populated by ``authenticate_user``, avoiding the
  ADC path entirely for pydata callers.

Idempotent and reversible: ``install_pydata_patch()`` can be called
many times; ``uninstall_pydata_patch()`` restores the original.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

LOGGER = logging.getLogger(__name__)

_INSTALLED = False
_ORIGINAL: Any | None = None


def install_pydata_patch() -> bool:
    """Patch ``pydata_google_auth.auth.get_colab_default_credentials``.

    Returns:
      ``True`` if the patch is now installed (either freshly or already
      installed before this call). ``False`` if ``pydata_google_auth``
      isn't importable, which is fine — code paths that don't use it
      don't need it.
    """
    global _INSTALLED, _ORIGINAL

    if _INSTALLED:
        return True

    try:
        import pydata_google_auth.auth as pga
    except ImportError:
        LOGGER.debug("pydata_google_auth not installed; skipping patch.")
        return False

    _ORIGINAL = getattr(pga, "get_colab_default_credentials", None)
    pga.get_colab_default_credentials = _patched_get_colab_default_credentials  # type: ignore[attr-defined]
    _INSTALLED = True
    LOGGER.debug("patched pydata_google_auth.auth.get_colab_default_credentials")
    return True


def uninstall_pydata_patch() -> None:
    """Undo ``install_pydata_patch``. No-op if not installed."""
    global _INSTALLED, _ORIGINAL

    if not _INSTALLED:
        return

    try:
        import pydata_google_auth.auth as pga
    except ImportError:
        _INSTALLED = False
        _ORIGINAL = None
        return

    if _ORIGINAL is not None:
        pga.get_colab_default_credentials = _ORIGINAL
    else:
        # The attribute didn't exist before; delete the patch.
        try:
            del pga.get_colab_default_credentials
        except AttributeError:
            pass

    _INSTALLED = False
    _ORIGINAL = None


def is_installed() -> bool:
    """Whether the pydata patch is currently active."""
    return _INSTALLED


def _patched_get_colab_default_credentials(
    scopes: Iterable[str],
) -> tuple[Any | None, str | None]:
    """Replacement for the vendor function.

    Contract matches pydata's expectation: returns
    ``(credentials, project_id)`` where ``credentials`` is either
    ``None`` (fall through to other auth methods) or a credential
    object with ``.token`` populated.
    """
    # Imports here, not at module top, to keep this module cheap when the
    # auth flow isn't actually exercised. Also breaks a potential import
    # cycle if pydata happens to import google.colab.* at import time.
    from google.colab import auth as colab_auth

    try:
        credentials = colab_auth.authenticate_user(_marimo_scopes=list(scopes))
    except colab_auth.AuthError as e:
        if e.code == "parent_unavailable":
            LOGGER.debug(
                "marimo-google-auth bridge unavailable; falling back to pydata auth"
            )
            return None, None
        LOGGER.warning("marimo-google-auth bridge failed in pydata patch: %s", e)
        return None, None
    except Exception as e:
        # Mirror pydata's tolerance: if anything fails, return (None, None)
        # so pydata can fall back to ``get_user_credentials`` paths.
        # But log at warning so the failure isn't silently swallowed.
        LOGGER.warning("marimo-google-auth bridge failed in pydata patch: %s", e)
        return None, None

    return credentials, None
