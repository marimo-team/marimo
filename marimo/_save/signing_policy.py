# Copyright 2026 Marimo. All rights reserved.
"""Resolve marimo config into a frozen cache-signing policy.

Trust is anchored from the merged config's user/env layers and the inherited
environment before any configured `.env` is loaded. Loaders read only the
frozen result. See `SigningPolicy`.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._save.signing import (
    DEFAULT_VERIFICATION,
    CacheSigner,
    fingerprint,
    normalize_fingerprint,
    normalize_verification,
)

if TYPE_CHECKING:
    from marimo._config.config import MarimoConfig

LOGGER = _loggers.marimo_logger()

# A PEM Ed25519 private key is well under 1 KiB; cap the read so a
# `private_key_path` pointed at a huge/streaming file can't hang or exhaust
# memory.
_MAX_KEY_FILE_BYTES = 64 * 1024

_PRIVATE_KEY_ENV = "MARIMO_CACHE_SIGNING_PRIVATE_KEY"
_PUBLIC_KEY_ENV = "MARIMO_CACHE_SIGNING_PUBLIC_KEY"


@dataclass(frozen=True)
class SigningPolicy:
    """The resolved cache-signing configuration for a session.

    Frozen so trust cannot drift between the check and the eventual
    `pickle.loads`, and so loading a `.env` afterwards cannot change it.
    `signer` and `trusted_signers` are resolved once at construction
    (including from the inherited environment). `state_key_path` is where a
    loader can load or mint the machine-local auto key.
    """

    verification: str = DEFAULT_VERIFICATION
    trusted_signers: frozenset[str] = field(default_factory=frozenset)
    # NB. compare=False: CacheSigner isn't a value type. The policy's identity
    # is its (verification, trust, key-path).
    signer: CacheSigner | None = field(default=None, compare=False)
    state_key_path: str | None = None

    @classmethod
    def from_config(cls, config: MarimoConfig) -> SigningPolicy:
        signing = config.get("signing") or {}
        cache = config.get("cache") or {}

        verification = normalize_verification(
            cache.get("verification", DEFAULT_VERIFICATION)
        )

        trusted = _resolve_trusted_signers(signing.get("trusted_signers"))
        # A public key in the inherited environment is a trusted *verifier*, not
        # this loader's own signing identity — record it as a trusted
        # fingerprint (so it must be named to be trusted) rather than an
        # implicitly-trusted own-signer that would auto-trust arbitrary writes.
        env_public = _env_public_fingerprint()
        if env_public is not None:
            trusted.add(env_public)

        signer = _resolve_write_signer(signing.get("private_key_path") or None)
        return cls(
            verification=verification,
            trusted_signers=frozenset(trusted),
            signer=signer,
            state_key_path=_default_state_key_path(),
        )


def _env_public_fingerprint() -> str | None:
    """Fingerprint of `MARIMO_CACHE_SIGNING_PUBLIC_KEY`, read from inherited env."""
    pem = os.environ.get(_PUBLIC_KEY_ENV)
    if not pem:
        return None
    try:
        return fingerprint(pem)
    except Exception as e:
        LOGGER.warning("Ignoring invalid %s: %s", _PUBLIC_KEY_ENV, e)
        return None


def _resolve_write_signer(private_key_path: str | None) -> CacheSigner | None:
    """Resolve the write identity from the config key path or the env key.

    Returns `None` when neither resolves or `cryptography` is unavailable.
    """
    from marimo._dependencies.dependencies import DependencyManager

    if not DependencyManager.cryptography.has():
        return None
    if private_key_path:
        signer = _load_signer_from_path(private_key_path)
        if signer is not None:
            return signer
    pem = os.environ.get(_PRIVATE_KEY_ENV)
    if pem:
        try:
            return CacheSigner.from_private_key_pem(pem)
        except Exception as e:
            LOGGER.warning("Ignoring invalid %s: %s", _PRIVATE_KEY_ENV, e)
    return None


def _default_state_key_path() -> str:
    from marimo._utils.xdg import marimo_state_dir

    return str(marimo_state_dir() / "cache_signing_key.pem")


def _load_signer_from_path(raw_path: str) -> CacheSigner | None:
    """Load a private-key signer from an absolute path, else `None`.

    Any failure (missing, oversized, malformed/encrypted/unsupported PEM)
    degrades to `None` uniformly rather than raising.
    """
    expanded = Path(raw_path).expanduser()
    # NB. reject relative paths: they resolve against the live CWD, where a
    # project can drop in a substitute key.
    if not expanded.is_absolute():
        LOGGER.warning(
            "signing.private_key_path %r must be an absolute path; ignoring "
            "and falling back to an auto-resolved signing identity.",
            raw_path,
        )
        return None
    try:
        return CacheSigner.from_private_key_pem(_read_key_file(str(expanded)))
    except Exception as e:
        LOGGER.warning(
            "Could not load signing.private_key_path %r (%s); falling back "
            "to an auto-resolved signing identity.",
            raw_path,
            e,
        )
        return None


def _read_key_file(path: str) -> str:
    """Read a small key file through a single fd, without following symlinks."""
    flags = os.O_RDONLY
    # O_NOFOLLOW is POSIX; absent on some platforms (e.g. Windows).
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise OSError("not a regular file")
        if st.st_size > _MAX_KEY_FILE_BYTES:
            raise OSError("file too large to be a PEM key")
        return os.read(fd, _MAX_KEY_FILE_BYTES + 1).decode()
    finally:
        os.close(fd)


def _resolve_trusted_signers(raw: Any) -> set[str]:
    """Normalize a config `trusted_signers` mapping into canonical fingerprints.

    Defensive: a malformed fingerprint is dropped with a warning rather than
    raising (unlike the loader kwarg), so one bad entry in a config file can't
    break the whole session. Two raw keys that canonicalize to the same
    fingerprint are warned about rather than silently collapsed.
    """
    if raw is None:
        return set()
    if not isinstance(raw, dict):
        LOGGER.warning(
            "signing.trusted_signers must be a table of "
            "{fingerprint = label}; ignoring %r.",
            type(raw).__name__,
        )
        return set()

    resolved: set[str] = set()
    for fp in raw:
        try:
            canonical = normalize_fingerprint(fp)
        except (ValueError, TypeError) as e:
            LOGGER.warning(
                "Ignoring invalid signing.trusted_signers entry %r: %s", fp, e
            )
            continue
        if canonical in resolved:
            LOGGER.warning(
                "Duplicate signing.trusted_signers fingerprint after "
                "normalization (%r); keeping one entry.",
                canonical,
            )
        resolved.add(canonical)
    return resolved


def get_signing_policy(
    current_path: str | None = None,
    *,
    config: MarimoConfig | None = None,
) -> SigningPolicy:
    """Resolve the effective cache-signing policy for the current session.

    Pass `config` — the kernel's effective, already-merged, unmasked config — to
    honor session / WASM-provided trust and mode. When omitted, the on-disk
    user/environment config is read (`hide_secrets=False` so the real
    `private_key_path` is visible).
    """
    if config is None:
        from marimo._config.manager import get_default_config_manager

        config = get_default_config_manager(
            current_path=current_path
        ).get_config(hide_secrets=False)
    return SigningPolicy.from_config(config)
