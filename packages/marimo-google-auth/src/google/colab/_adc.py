"""Application Default Credentials (ADC) file + scope sidecar writers.

After the auth bridge round-trip succeeds, we have a short-lived access
token in the kernel. To make every Google client library (``gdrive_fsspec``,
``google-cloud-storage``, ``google-cloud-bigquery``, …) pick it up
without per-library plumbing, we write standard ADC files:

1. ``~/.config/gcloud/application_default_credentials.json`` in
   ``authorized_user`` format. This is what ``google.auth.default()``
   looks for after the env var.
2. A sidecar at
   ``~/.config/marimo-google-auth/granted_scopes.json`` recording which
   scopes were granted and when, so subsequent calls can detect a scope
   mismatch and re-prompt.

Refresh-token model
-------------------
``authorized_user`` ADC requires a ``refresh_token`` field. We never
have a real one to write here: in molab Clerk holds the refresh token
server-side, and the self-hosted GIS popup path doesn't mint refresh
tokens to the browser at all. We write a sentinel ``refresh_token``
value (see ``_REFRESH_TOKEN_SENTINEL`` below); google-auth happily
reads the file and surfaces the access token via
``Credentials.token``. A library that actually tries to refresh by
hitting Google's OAuth endpoint will fail — by design. The patch in
``_patch.py`` sidesteps this by constructing a fresh ``Credentials``
on every ``get_colab_default_credentials`` call, which re-issues the
stdin round-trip when the cached token has expired. That keeps the
refresh path inside the bridge instead of inside google-auth.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

LOGGER = logging.getLogger(__name__)

# Stable sentinels so that downstream tooling — and humans grepping
# memory dumps or filesystem snapshots — can immediately tell our ADC
# apart from a real ``gcloud auth application-default login``
# credential.
#
# These values are deliberately shaped to be **unmistakable**:
#
#   - The refresh_token sentinel uses an ``ALL_CAPS:WITH_COLONS``
#     format. Real Google refresh tokens start with ``1//`` followed
#     by 100+ base64-ish chars (`A-Z`, `a-z`, `0-9`, `-`, `_`). They
#     never contain colons. A leaked sentinel triggers "obviously a
#     placeholder" pattern-matching on first inspection.
#   - The client_id sentinel still ends in
#     ``.apps.googleusercontent.com`` so google-auth doesn't bail on a
#     shape check at parse time, but contains ``.stub.`` in the
#     middle so it's instantly clear it isn't a real OAuth client.
#   - The client_secret sentinel is short and self-describing; real
#     secrets are 24-char base64-ish opaque strings.
#
# None of these values are ever transmitted to Google (we never call
# the refresh endpoint with them — see module docstring). The
# sentinels exist purely so that an attacker who manages to
# exfiltrate the ADC file can't mistake the placeholder for a real
# token and waste their (and our) time trying to use it.
_REFRESH_TOKEN_SENTINEL = (
    "MARIMO_GOOGLE_AUTH:NOT_A_REAL_REFRESH_TOKEN:RPC_BRIDGE_HANDLES_REFRESH"
)
_CLIENT_ID_SENTINEL = "marimo-google-auth.stub.apps.googleusercontent.com"
_CLIENT_SECRET_SENTINEL = "MARIMO_GOOGLE_AUTH:NOT_A_REAL_CLIENT_SECRET"

# Custom (non-default) ADC paths we have set ``GOOGLE_APPLICATION_CREDENTIALS``
# to during this process. When ``write_adc`` later writes to the *default* ADC
# path, we use this set to detect (and unset) a stale env var we own —
# without ever clobbering a service-account key the user pointed the env var
# at themselves.
_ENV_VAR_PATHS_WE_OWN: set[str] = set()


def default_adc_path() -> Path:
    """Standard ADC discovery path used by ``google.auth.default()``.

    Matches gcloud's behavior on POSIX. We don't try to be clever about
    Windows here — marimo's notebook kernels run on POSIX in molab and
    in every self-hosted deployment we've seen.
    """
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def default_sidecar_path() -> Path:
    """Path of the granted-scopes sidecar that our shim manages."""
    return Path.home() / ".config" / "marimo-google-auth" / "granted_scopes.json"


def write_adc(
    *,
    access_token: str,
    expires_at: int,
    scopes: Sequence[str],
    adc_path: Path | None = None,
    sidecar_path: Path | None = None,
) -> Path:
    """Write the ADC file + sidecar.

    Returns the resolved ADC path. If ``adc_path`` is non-default,
    also sets ``GOOGLE_APPLICATION_CREDENTIALS`` so that
    ``google.auth.default()`` discovers it first.
    """
    resolved_adc = adc_path or default_adc_path()
    resolved_sidecar = sidecar_path or default_sidecar_path()

    resolved_adc.parent.mkdir(parents=True, exist_ok=True)
    resolved_sidecar.parent.mkdir(parents=True, exist_ok=True)

    adc_doc = {
        "type": "authorized_user",
        "client_id": _CLIENT_ID_SENTINEL,
        "client_secret": _CLIENT_SECRET_SENTINEL,
        "refresh_token": _REFRESH_TOKEN_SENTINEL,
        # Non-standard fields, but harmless: google-auth ignores them.
        # Storing the access token lets us short-circuit refresh on first
        # use via the credential factory in ``auth.py``.
        "access_token": access_token,
        "expires_at": expires_at,
        "scopes": list(scopes),
        "issued_by": "marimo-google-auth",
    }

    sidecar_doc = {
        "version": 1,
        "scopes": list(scopes),
        "access_token_expires_at": expires_at,
        "written_at": int(time.time()),
    }

    _atomic_write_json(resolved_adc, adc_doc, mode=0o600)
    _atomic_write_json(resolved_sidecar, sidecar_doc, mode=0o600)

    # google.auth.default() reads GOOGLE_APPLICATION_CREDENTIALS
    # first, so point it at a non-default ADC, and clear it when we
    # revert to the default path (but only if we set it ourselves —
    # never clobber a user-provided service-account key).
    if resolved_adc != default_adc_path():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(resolved_adc)
        _ENV_VAR_PATHS_WE_OWN.add(str(resolved_adc))
        LOGGER.debug("set GOOGLE_APPLICATION_CREDENTIALS=%s", resolved_adc)
    else:
        current = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if current is not None and current in _ENV_VAR_PATHS_WE_OWN:
            os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
            _ENV_VAR_PATHS_WE_OWN.discard(current)
            LOGGER.debug(
                "cleared stale GOOGLE_APPLICATION_CREDENTIALS=%s "
                "(we now write to the default ADC path)",
                current,
            )

    return resolved_adc


def read_sidecar_scopes(
    sidecar_path: Path | None = None,
) -> list[str]:
    """Read the scopes previously granted, or empty list if no sidecar yet."""
    path = sidecar_path or default_sidecar_path()
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        LOGGER.warning("failed to read scopes sidecar at %s: %s", path, e)
        return []
    scopes = doc.get("scopes")
    if not isinstance(scopes, list):
        return []
    return [s for s in scopes if isinstance(s, str)]


def missing_scopes(
    requested: Iterable[str], sidecar_path: Path | None = None
) -> list[str]:
    """Return the subset of ``requested`` not present in the sidecar."""
    granted = set(read_sidecar_scopes(sidecar_path))
    return [s for s in requested if s not in granted]


def _atomic_write_json(path: Path, doc: dict, *, mode: int = 0o600) -> None:
    """Write ``doc`` to ``path`` atomically with a restrictive mode."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    serialized = json.dumps(doc, indent=2, sort_keys=True)
    # Open with restrictive mode from the start to avoid a race where the
    # file briefly exists at the default umask.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    os.replace(tmp, path)
    # os.replace preserves mode on POSIX; double-check on systems where
    # the umask might have lowered it.
    try:
        os.chmod(path, mode)
    except OSError:
        # Best-effort; not all filesystems support chmod.
        pass
