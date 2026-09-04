# Copyright 2026 Marimo. All rights reserved.
"""Ed25519 signing and blob-hash verification for LazyLoader cache manifests.

This module is importable without the `cryptography` package — all
`cryptography` imports are deferred inside methods so consumers that do not
use signing incur no import cost.
"""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

# Verification posture, shared by the config resolver (`signing_policy`) and
# the loader (`loaders.lazy`). `off`: no signing or verification (legacy
# opt-out). `on` (default): sign on write, and on read serve only entries that
# verify against a trusted key — unverifiable entries miss and recompute
# (fail-safe). `strict`: like `on`, but an unverifiable entry raises
# (fail-closed).
VALID_VERIFICATIONS = ("off", "on", "strict")
DEFAULT_VERIFICATION = "on"


class CacheSignatureError(Exception):
    """Raised when Ed25519 or blob-hash verification fails.

    Untrusted bytes are **not** returned — the error surfaces before any
    deserialization so that a poisoned cache entry cannot execute arbitrary
    code via `pickle.loads`.
    """


def _sha256hex(data: bytes) -> str:
    """Return the hex-encoded SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def normalize_verification(raw: Any, *, strict: bool = False) -> str:
    """Validate a verification posture.

    With `strict=False` (config files) an unrecognized value warns and degrades
    to the default rather than breaking the session; with `strict=True` (a
    caller-supplied kwarg) it raises. The default is fail-safe — unverifiable
    entries recompute — so the degrade path never widens what gets
    deserialized.
    """
    if isinstance(raw, str) and raw in VALID_VERIFICATIONS:
        return raw
    expected = ", ".join(VALID_VERIFICATIONS)
    if strict:
        raise ValueError(
            f"Invalid cache verification {raw!r}; expected one of {expected}."
        )
    from marimo import _loggers

    _loggers.marimo_logger().warning(
        "Invalid cache verification %r; expected one of %s. Falling back to %r.",
        raw,
        expected,
        DEFAULT_VERIFICATION,
    )
    return DEFAULT_VERIFICATION


class CacheSigner:
    """Ed25519 signing and verification for LazyLoader cache manifests.

    Private key signs; consumers only need the public key to verify.
    All `cryptography` imports are deferred so this module is importable
    without the package installed.

    Typical usage::

        from marimo._save.signing import CacheSigner, generate_keypair

        private_pem, public_pem = generate_keypair()

        # Publisher — signs on write
        writer = LazyLoader.partial(
            signer=CacheSigner.from_private_key_pem(private_pem)
        )

        # Consumer — verifies signed entries; unverifiable entries miss
        # (recompute) rather than being served (fail-safe, verification="on")
        reader = LazyLoader.partial(
            signer=CacheSigner.from_public_key_pem(public_pem)
        )

        # Consumer — strict: raises on any unsigned/unverifiable entry
        reader_strict = LazyLoader.partial(
            signer=CacheSigner.from_public_key_pem(public_pem),
            verification="strict",
        )

    Keys can also be loaded from environment variables::

        loader = LazyLoader.partial(signer=CacheSigner.from_env())
    """

    def __init__(
        self,
        private_key: Any = None,
        public_key: Any = None,
    ) -> None:
        if private_key is None and public_key is None:
            raise ValueError(
                "CacheSigner requires at least one of private_key or public_key"
            )
        self._private_key: Any = private_key
        self._public_key: Any = (
            public_key if public_key is not None else private_key.public_key()
        )

    @property
    def can_sign(self) -> bool:
        """True when a private key is available for signing."""
        return self._private_key is not None

    def sign(self, data: bytes) -> str:
        """Sign *data* and return a base64url-encoded Ed25519 signature."""
        if self._private_key is None:
            raise ValueError("Cannot sign: no private key configured")
        return base64.urlsafe_b64encode(self._private_key.sign(data)).decode()

    def verify(self, data: bytes, signature: str) -> None:
        """Verify *signature* against *data*.

        Raises :class:`CacheSignatureError` when the signature is invalid,
        including when the signature string is not valid base64.
        """
        import binascii

        from cryptography.exceptions import InvalidSignature

        try:
            # validate=True so a malformed signature raises deterministically
            # here rather than decoding to junk that fails verification later.
            sig_bytes = base64.b64decode(
                signature, altchars=b"-_", validate=True
            )
        except (binascii.Error, ValueError) as e:
            raise CacheSignatureError(
                "A cache entry could not be verified — its signature field is "
                "not readable. The cached data may be corrupted or was edited "
                "outside of marimo.\n"
                "To recover, call cache_clear() on the cached function or "
                "context manager."
            ) from e

        try:
            self._public_key.verify(sig_bytes, data)
        except InvalidSignature as e:
            raise CacheSignatureError(
                "A cache entry's signature does not match its contents — the "
                "cached data may be corrupted or was modified outside of "
                "marimo.\n"
                "To recover, call cache_clear() on the cached function or "
                "context manager."
            ) from e

    def verify_blob(
        self, blob_key: str, blob_bytes: bytes, expected_hex: str
    ) -> None:
        """Verify that *blob_bytes* match the signed hash *expected_hex*.

        Raises :class:`CacheSignatureError` when the hashes differ.  This is
        called **before** `pickle.loads` so that a tampered blob cannot
        execute arbitrary code.
        """
        actual = _sha256hex(blob_bytes)
        if actual != expected_hex:
            raise CacheSignatureError(
                f"A cached file's contents don't match the expected checksum "
                f"(file: {blob_key!r}). The data may be corrupted or was "
                f"modified outside of marimo.\n"
                f"To recover, call cache_clear() on the cached function or "
                f"context manager."
            )

    def fingerprint(self) -> str:
        """Return the SSH-style SHA-256 fingerprint of this signer's key.

        The single trust primitive: two signers with the same fingerprint hold
        the same public key.  See the module-level :func:`fingerprint`.
        """
        return fingerprint(self.public_key_pem())

    @classmethod
    def from_private_key_pem(cls, pem: str) -> CacheSigner:
        """Load a signer from a PEM-encoded Ed25519 private key.

        Raises `ValueError` if the PEM is not an Ed25519 key — a non-Ed25519
        key would otherwise load fine and only fail later at `sign()`/
        `verify()` (surfacing as a generic cache miss).
        """
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key,
        )

        private_key = load_pem_private_key(pem.encode(), password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise ValueError(
                "Cache signing requires an Ed25519 private key, got "
                f"{type(private_key).__name__}."
            )
        return cls(private_key=private_key)

    @classmethod
    def from_public_key_pem(cls, pem: str) -> CacheSigner:
        """Load a verifier from a PEM-encoded Ed25519 public key.

        Raises `ValueError` if the PEM is not an Ed25519 key.
        """
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
        from cryptography.hazmat.primitives.serialization import (
            load_pem_public_key,
        )

        public_key = load_pem_public_key(pem.encode())
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError(
                "Cache signing requires an Ed25519 public key, got "
                f"{type(public_key).__name__}."
            )
        return cls(public_key=public_key)

    @classmethod
    def from_env(
        cls,
        private_key_env: str = "MARIMO_CACHE_SIGNING_PRIVATE_KEY",
        public_key_env: str = "MARIMO_CACHE_SIGNING_PUBLIC_KEY",
    ) -> CacheSigner | None:
        """Construct a signer from environment variables.

        Returns `None` when neither variable is set so callers can write::

            signer = CacheSigner.from_env()
            loader = LazyLoader.partial(signer=signer)
        """
        import os

        if pem := os.environ.get(private_key_env):
            return cls.from_private_key_pem(pem)
        if pem := os.environ.get(public_key_env):
            return cls.from_public_key_pem(pem)
        return None

    def public_key_pem(self) -> str:
        """Return the PEM-encoded public key."""
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        result: str = self._public_key.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode()
        return result

    def private_key_pem(self) -> str:
        """Return the PEM-encoded private key.

        Raises `ValueError` when only a public key was provided.
        """
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PrivateFormat,
        )

        if self._private_key is None:
            raise ValueError("No private key available")
        result: str = self._private_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        ).decode()
        return result


def fingerprint(public_key_pem: str) -> str:
    """Return the SSH-style SHA-256 fingerprint of an Ed25519 public key PEM.

    Format: `"SHA256:" + base64(sha256(DER SubjectPublicKeyInfo))` with the
    trailing base64 padding stripped, matching how OpenSSH presents key
    fingerprints.  This is the single trust primitive — config lists and the
    per-loader `trusted_signers` set hold these strings, while the full key
    travels in the manifest, so a compact fingerprint pins a full key without
    bloating configuration.

    Raises `ValueError` when *public_key_pem* is not an Ed25519 public key.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
        load_pem_public_key,
    )

    key = load_pem_public_key(public_key_pem.encode())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError(
            "Cache signing requires an Ed25519 public key, got "
            f"{type(key).__name__}."
        )
    der = key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return "SHA256:" + base64.b64encode(
        hashlib.sha256(der).digest()
    ).decode().rstrip("=")


_FP_URLSAFE_TO_STD = str.maketrans("-_", "+/")


def normalize_fingerprint(fp: str) -> str:
    """Validate and canonicalize one `"SHA256:<base64>"` fingerprint.

    Accepts standard or urlsafe base64, padded or unpadded, and returns the
    canonical form produced by :func:`fingerprint` (standard base64, no
    padding). Raising on a malformed digest here turns a fat-fingered
    fingerprint into a configuration-time error rather than a permanent, silent
    cache miss (the digest would validate on prefix alone but never match a
    real key).
    """
    import binascii

    if not isinstance(fp, str) or not fp.startswith("SHA256:"):
        raise ValueError(
            f"Invalid trusted_signers fingerprint {fp!r}; expected "
            "'SHA256:<base64>' as produced by "
            "marimo._save.signing.fingerprint()."
        )
    body = fp[len("SHA256:") :].translate(_FP_URLSAFE_TO_STD).rstrip("=")
    try:
        raw = base64.b64decode(body + "=" * (-len(body) % 4), validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError(
            f"Invalid trusted_signers fingerprint {fp!r}; the digest is "
            "not valid base64."
        ) from e
    if len(raw) != 32:
        raise ValueError(
            f"Invalid trusted_signers fingerprint {fp!r}; expected a "
            f"SHA-256 (32-byte) digest, got {len(raw)} byte(s)."
        )
    # Re-encode from the decoded bytes rather than returning `body` verbatim.
    # base64 of 32 bytes has 2 unused ("slack") bits in the final character, so
    # several distinct final characters decode to the same digest. Returning the
    # raw text lets such a variant validate here yet never match the canonical
    # form, which is a permanent silent miss.
    return "SHA256:" + base64.b64encode(raw).decode("ascii").rstrip("=")


def normalize_fingerprints(value: Iterable[str] | None) -> set[str]:
    """Validate and collect `trusted_signers` fingerprint strings.

    Rejects a bare `str` (which would otherwise iterate into single
    characters — a silent-miss footgun) and canonicalizes each entry via
    :func:`normalize_fingerprint` so a padded or urlsafe paste still matches
    :func:`fingerprint` output.
    """
    if value is None:
        return set()
    if isinstance(value, str):
        raise TypeError(
            "trusted_signers must be an iterable of fingerprint strings, not "
            "a single str. Wrap it in a set/list: trusted_signers={fp}."
        )
    return {normalize_fingerprint(fp) for fp in value}


def generate_keypair() -> tuple[str, str]:
    """Generate an Ed25519 key pair for cache signing.

    Returns `(private_key_pem, public_key_pem)`.  Keep the private key
    secret; distribute the public key to cache consumers.

    Example::

        private_pem, public_pem = generate_keypair()
        # Store private_pem securely; share public_pem with readers.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    key = Ed25519PrivateKey.generate()
    signer = CacheSigner(private_key=key)
    return signer.private_key_pem(), signer.public_key_pem()


def _get_default_signer(auto_generate: bool = True) -> CacheSigner | None:
    """Resolve the default cache signer for a session with no frozen policy.

    Resolution order:

    1. `MARIMO_CACHE_SIGNING_PRIVATE_KEY` env var → private-key signer
    2. `MARIMO_CACHE_SIGNING_PUBLIC_KEY` env var → public-key (verify-only) signer
    3. `marimo_state_dir() / "cache_signing_key.pem"` → load saved private key
    4. Neither set → generate a fresh Ed25519 key, save it, return signer

    Reads the environment live, so it is only for contexts that have no
    frozen policy. Returns `None` when `cryptography` is not installed.
    """
    from marimo._dependencies.dependencies import DependencyManager

    if not DependencyManager.cryptography.has():
        return None

    # 1 & 2: env vars take precedence
    signer = CacheSigner.from_env()
    if signer is not None:
        return signer

    return _get_machine_signer(auto_generate=auto_generate)


def _get_machine_signer(
    key_path: str | None = None, auto_generate: bool = True
) -> CacheSigner | None:
    """Load (or, if *auto_generate*, mint) the machine-local signing key.

    `key_path` defaults to `marimo_state_dir() / "cache_signing_key.pem"`. A
    caller passes an explicit path to avoid re-resolving the state directory
    from a possibly-polluted live environment. Does not read signing env vars.
    `auto_generate=False` skips minting (shared/remote stores, whose auto key
    is unverifiable elsewhere). Returns `None` when `cryptography` is
    unavailable.
    """
    import logging
    import os
    import stat
    from pathlib import Path

    from marimo._dependencies.dependencies import DependencyManager

    if not DependencyManager.cryptography.has():
        return None

    if not auto_generate:
        return None

    if key_path is None:
        from marimo._utils.xdg import marimo_state_dir

        key_file = marimo_state_dir() / "cache_signing_key.pem"
    else:
        key_file = Path(key_path)
    if key_file.exists():
        try:
            signer = CacheSigner.from_private_key_pem(key_file.read_text())
            # Best-effort: re-tighten perms in case the key was created before
            # we chmod'd it (or by another tool) — it's a private signing key.
            try:
                os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
            return signer
        except Exception:
            logging.getLogger("marimo").warning(
                "Failed to load cache signing key from %s. "
                "Restore the key or remove the file to generate a new identity.",
                key_file,
            )
            return None

    # Publish a complete key without replacing an identity another process
    # already uses. Atomic replacement alone lets concurrent first-time
    # writers adopt different keys before the last replacement wins.
    import tempfile

    try:
        private_pem, _ = generate_keypair()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=key_file.parent, prefix=".cache_key_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as file:
                file.write(private_pem)
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
            try:
                os.link(tmp, key_file)
            except FileExistsError:
                # The winner published its complete key before creating the
                # link, so every caller can now adopt the same identity.
                pass
            else:
                logging.getLogger("marimo").info(
                    "Generated cache signing key: %s", key_file
                )
        finally:
            os.unlink(tmp)
        return CacheSigner.from_private_key_pem(key_file.read_text())
    except Exception:
        logging.getLogger("marimo").warning(
            "Could not persist cache signing key to %s; "
            "verified cache writes will be skipped for this session.",
            key_file,
        )
        return None
