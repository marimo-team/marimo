# Copyright 2026 Marimo. All rights reserved.
"""Unit tests for marimo._save.signing."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest

pytest.importorskip("cryptography", reason="cryptography not installed")

from marimo._save.signing import (
    CacheSignatureError,
    CacheSigner,
    _sha256hex,
    fingerprint,
    generate_keypair,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signer() -> CacheSigner:
    private_pem, _ = generate_keypair()
    return CacheSigner.from_private_key_pem(private_pem)


def _make_verifier() -> tuple[CacheSigner, CacheSigner]:
    """Return (signer_with_private, verifier_with_public_only)."""
    private_pem, public_pem = generate_keypair()
    signer = CacheSigner.from_private_key_pem(private_pem)
    verifier = CacheSigner.from_public_key_pem(public_pem)
    return signer, verifier


# ---------------------------------------------------------------------------
# generate_keypair
# ---------------------------------------------------------------------------


class TestGenerateKeypair:
    def test_returns_two_pem_strings(self) -> None:
        private_pem, public_pem = generate_keypair()
        assert "PRIVATE KEY" in private_pem
        assert "PUBLIC KEY" in public_pem

    def test_pem_round_trip(self) -> None:
        private_pem, public_pem = generate_keypair()
        signer = CacheSigner.from_private_key_pem(private_pem)
        assert signer.private_key_pem() == private_pem
        assert signer.public_key_pem() == public_pem


# ---------------------------------------------------------------------------
# CacheSigner construction
# ---------------------------------------------------------------------------


class TestCacheSignerConstruction:
    def test_requires_at_least_one_key(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            CacheSigner()

    def test_private_key_implies_public(self) -> None:
        signer = _make_signer()
        assert signer.can_sign
        # Public key is derived automatically; PEM export should work.
        pem = signer.public_key_pem()
        assert "PUBLIC KEY" in pem

    def test_public_key_only(self) -> None:
        _, public_pem = generate_keypair()
        verifier = CacheSigner.from_public_key_pem(public_pem)
        assert not verifier.can_sign

    def test_sign_without_private_key_raises(self) -> None:
        _, public_pem = generate_keypair()
        verifier = CacheSigner.from_public_key_pem(public_pem)
        with pytest.raises(ValueError, match="no private key"):
            verifier.sign(b"data")

    def test_private_key_pem_without_private_raises(self) -> None:
        _, public_pem = generate_keypair()
        verifier = CacheSigner.from_public_key_pem(public_pem)
        with pytest.raises(ValueError, match="No private key"):
            verifier.private_key_pem()

    def test_from_public_key_pem_rejects_non_ed25519(self) -> None:
        """A non-Ed25519 key must fail at load, not silently at verify time."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        ec_pub = (
            ec.generate_private_key(ec.SECP256R1())
            .public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        with pytest.raises(ValueError, match="Ed25519"):
            CacheSigner.from_public_key_pem(ec_pub)

    def test_from_private_key_pem_rejects_non_ed25519(self) -> None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        ec_priv = (
            ec.generate_private_key(ec.SECP256R1())
            .private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
            .decode()
        )
        with pytest.raises(ValueError, match="Ed25519"):
            CacheSigner.from_private_key_pem(ec_priv)


# ---------------------------------------------------------------------------
# sign / verify
# ---------------------------------------------------------------------------


class TestSignVerify:
    def test_sign_and_verify_succeed(self) -> None:
        signer, verifier = _make_verifier()
        data = b"hello world"
        sig = signer.sign(data)
        # Must not raise
        verifier.verify(data, sig)

    def test_tampered_data_raises(self) -> None:
        signer, verifier = _make_verifier()
        sig = signer.sign(b"original")
        with pytest.raises(CacheSignatureError):
            verifier.verify(b"tampered", sig)

    def test_tampered_signature_raises(self) -> None:
        signer, verifier = _make_verifier()
        # Sign different data to get a valid but wrong signature
        bad_sig = signer.sign(b"completely different data")
        with pytest.raises(CacheSignatureError):
            verifier.verify(b"data", bad_sig)

    def test_wrong_key_raises(self) -> None:
        signer, _ = _make_verifier()
        _, other_verifier = _make_verifier()
        sig = signer.sign(b"data")
        with pytest.raises(CacheSignatureError):
            other_verifier.verify(b"data", sig)

    def test_self_verify(self) -> None:
        """A signer with private key can also verify its own signatures."""
        signer = _make_signer()
        data = b"test"
        sig = signer.sign(data)
        signer.verify(data, sig)  # must not raise

    def test_malformed_base64_raises(self) -> None:
        """Truncated/corrupted base64 in the signature string raises CacheSignatureError."""
        _, verifier = _make_verifier()
        with pytest.raises(
            CacheSignatureError, match="not readable|corrupted"
        ):
            verifier.verify(b"data", "not!!valid==base64@@")


# ---------------------------------------------------------------------------
# verify_blob
# ---------------------------------------------------------------------------


class TestVerifyBlob:
    def test_correct_hash_passes(self) -> None:
        signer = _make_signer()
        blob = b"blob content"
        expected = _sha256hex(blob)
        signer.verify_blob("key", blob, expected)  # must not raise

    def test_wrong_hash_raises(self) -> None:
        signer = _make_signer()
        blob = b"blob content"
        wrong_hash = _sha256hex(b"different content")
        with pytest.raises(CacheSignatureError, match="checksum"):
            signer.verify_blob("key", blob, wrong_hash)

    def test_error_message_contains_key(self) -> None:
        signer = _make_signer()
        with pytest.raises(CacheSignatureError, match="my_blob_key"):
            signer.verify_blob("my_blob_key", b"x", "0" * 64)


# ---------------------------------------------------------------------------
# _sha256hex
# ---------------------------------------------------------------------------


class TestSha256Hex:
    def test_known_value(self) -> None:
        # SHA-256 of empty bytes is well-known
        assert _sha256hex(b"") == (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_returns_64_chars(self) -> None:
        assert len(_sha256hex(b"anything")) == 64


# ---------------------------------------------------------------------------
# from_env
# ---------------------------------------------------------------------------


class TestFromEnv:
    def test_returns_none_when_not_set(self) -> None:
        with patch.dict(
            os.environ,
            {},
            clear=False,
        ):
            # Ensure vars aren't set in the environment
            env = {
                k: v
                for k, v in os.environ.items()
                if k
                not in (
                    "MARIMO_CACHE_SIGNING_PRIVATE_KEY",
                    "MARIMO_CACHE_SIGNING_PUBLIC_KEY",
                )
            }
            with patch.dict(os.environ, env, clear=True):
                result = CacheSigner.from_env()
        assert result is None

    def test_private_key_env_takes_precedence(self) -> None:
        private_pem, public_pem = generate_keypair()
        with patch.dict(
            os.environ,
            {
                "MARIMO_CACHE_SIGNING_PRIVATE_KEY": private_pem,
                "MARIMO_CACHE_SIGNING_PUBLIC_KEY": public_pem,
            },
        ):
            signer = CacheSigner.from_env()
        assert signer is not None
        assert signer.can_sign

    def test_public_key_only_env(self) -> None:
        _, public_pem = generate_keypair()
        env_without_private = {
            k: v
            for k, v in os.environ.items()
            if k != "MARIMO_CACHE_SIGNING_PRIVATE_KEY"
        }
        env_without_private["MARIMO_CACHE_SIGNING_PUBLIC_KEY"] = public_pem
        with patch.dict(os.environ, env_without_private, clear=True):
            signer = CacheSigner.from_env()
        assert signer is not None
        assert not signer.can_sign

    def test_custom_env_var_names(self) -> None:
        private_pem, _ = generate_keypair()
        with patch.dict(os.environ, {"MY_PRIV": private_pem}):
            signer = CacheSigner.from_env(
                private_key_env="MY_PRIV", public_key_env="MY_PUB"
            )
        assert signer is not None
        assert signer.can_sign


class TestFingerprint:
    def test_format_unpadded_sha256(self) -> None:
        _, pub = generate_keypair()
        fp = fingerprint(pub)
        assert fp.startswith("SHA256:")
        assert "=" not in fp

    def test_matches_signer_method(self) -> None:
        priv, pub = generate_keypair()
        signer = CacheSigner.from_private_key_pem(priv)
        assert signer.fingerprint() == fingerprint(pub)

    def test_deterministic_and_distinct(self) -> None:
        _, pub_a = generate_keypair()
        _, pub_b = generate_keypair()
        assert fingerprint(pub_a) == fingerprint(pub_a)
        assert fingerprint(pub_a) != fingerprint(pub_b)

    def test_rejects_garbage_pem(self) -> None:
        with pytest.raises(ValueError):
            fingerprint(
                "-----BEGIN PUBLIC KEY-----\nnope\n-----END PUBLIC KEY-----"
            )


class TestGetDefaultSigner:
    def test_returns_none_without_cryptography(self) -> None:
        from marimo._save.signing import _get_default_signer

        with patch(
            "marimo._dependencies.dependencies.DependencyManager.cryptography.has",
            return_value=False,
        ):
            assert _get_default_signer() is None

    def test_env_var_takes_precedence(self) -> None:
        from marimo._save.signing import _get_default_signer

        private_pem, _ = generate_keypair()
        with patch.dict(
            os.environ,
            {"MARIMO_CACHE_SIGNING_PRIVATE_KEY": private_pem},
        ):
            signer = _get_default_signer()
            assert signer is not None
            assert signer.can_sign

    def test_generates_and_persists_key(self, tmp_path: Any) -> None:
        from marimo._save.signing import _get_default_signer

        key_path = tmp_path / "cache_signing_key.pem"

        # Ensure env vars don't interfere
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in (
                "MARIMO_CACHE_SIGNING_PRIVATE_KEY",
                "MARIMO_CACHE_SIGNING_PUBLIC_KEY",
            )
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch(
                "marimo._utils.xdg.marimo_state_dir",
                return_value=tmp_path,
            ),
        ):
            signer = _get_default_signer()
            assert signer is not None
            assert signer.can_sign
            assert key_path.exists()
            # Key file should be readable and produce the same public key
            loaded = CacheSigner.from_private_key_pem(key_path.read_text())
            assert loaded.public_key_pem() == signer.public_key_pem()

    def test_loads_existing_key(self, tmp_path: Any) -> None:
        from marimo._save.signing import _get_default_signer

        # Pre-create a key file
        private_pem, _ = generate_keypair()
        key_path = tmp_path / "cache_signing_key.pem"
        key_path.write_text(private_pem)

        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in (
                "MARIMO_CACHE_SIGNING_PRIVATE_KEY",
                "MARIMO_CACHE_SIGNING_PUBLIC_KEY",
            )
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch(
                "marimo._utils.xdg.marimo_state_dir",
                return_value=tmp_path,
            ),
        ):
            signer = _get_default_signer()
            assert signer is not None
            # Should load the existing key, not generate a new one
            assert (
                signer.public_key_pem()
                == CacheSigner.from_private_key_pem(
                    private_pem
                ).public_key_pem()
            )

    def test_corrupt_key_file_regenerates(self, tmp_path: Any) -> None:
        from marimo._save.signing import _get_default_signer

        key_path = tmp_path / "cache_signing_key.pem"
        key_path.write_text("not a valid PEM")

        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in (
                "MARIMO_CACHE_SIGNING_PRIVATE_KEY",
                "MARIMO_CACHE_SIGNING_PUBLIC_KEY",
            )
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch(
                "marimo._utils.xdg.marimo_state_dir",
                return_value=tmp_path,
            ),
        ):
            signer = _get_default_signer()
            assert signer is not None
            assert signer.can_sign
            # Should have overwritten the corrupt file
            assert key_path.exists()
            assert "PRIVATE KEY" in key_path.read_text()
