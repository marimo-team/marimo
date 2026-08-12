# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os

import pytest

from marimo._save.cache import CacheState
from marimo._save.signing import fingerprint, generate_keypair
from marimo._save.signing_policy import (
    SigningPolicy,
    _resolve_trusted_signers,
)
from marimo._save.stores import DEFAULT_STORE


@pytest.fixture
def keypair() -> tuple[str, str, str]:
    pytest.importorskip("cryptography")
    priv, pub = generate_keypair()
    return priv, pub, fingerprint(pub)


@pytest.fixture(autouse=True)
def _clear_signing_env(monkeypatch) -> None:
    # The policy reads signing env vars at freeze; keep tests hermetic.
    monkeypatch.delenv("MARIMO_CACHE_SIGNING_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("MARIMO_CACHE_SIGNING_PUBLIC_KEY", raising=False)


class TestSigningPolicyFromConfig:
    def test_empty_config_defaults(self) -> None:
        policy = SigningPolicy.from_config({})
        assert policy.verification == "on"
        assert policy.trusted_signers == frozenset()
        assert policy.signer is None
        # The machine-key path is frozen at construction, not read live later.
        assert policy.state_key_path is not None

    def test_verification_passthrough(self) -> None:
        assert SigningPolicy.from_config(
            {"cache": {"verification": "strict"}}
        ).verification == ("strict")
        assert SigningPolicy.from_config(
            {"cache": {"verification": "off"}}
        ).verification == ("off")

    def test_invalid_verification_falls_back_to_on(self) -> None:
        policy = SigningPolicy.from_config(
            {"cache": {"verification": "bogus"}}
        )
        assert policy.verification == "on"

    def test_trusted_signers_normalized(self, keypair) -> None:
        _priv, pub, fp = keypair
        # urlsafe, padded variant must canonicalize to fingerprint() output.
        urlsafe = "SHA256:" + fp[len("SHA256:") :].replace("+", "-").replace(
            "/", "_"
        )
        policy = SigningPolicy.from_config(
            {"signing": {"trusted_signers": {urlsafe: "alice"}}}
        )
        assert policy.trusted_signers == frozenset({fp})

    def test_malformed_fingerprints_dropped(self, keypair) -> None:
        _priv, _pub, fp = keypair
        policy = SigningPolicy.from_config(
            {
                "signing": {
                    "trusted_signers": {
                        fp: "good",
                        "SHA256:not-valid-base64!!": "bad",
                        "no-prefix": "bad",
                    }
                }
            }
        )
        assert policy.trusted_signers == frozenset({fp})

    def test_non_dict_trusted_signers_ignored(self) -> None:
        policy = SigningPolicy.from_config(
            {"signing": {"trusted_signers": ["SHA256:whatever"]}}
        )
        assert policy.trusted_signers == frozenset()

    def test_private_key_path_resolves_to_signer(
        self, keypair, tmp_path
    ) -> None:
        priv, _pub, fp = keypair
        key_file = tmp_path / "key.pem"
        key_file.write_text(priv)
        # The concrete signer is resolved eagerly at freeze (not lazily).
        policy = SigningPolicy.from_config(
            {"signing": {"private_key_path": str(key_file)}}
        )
        assert policy.signer is not None
        assert policy.signer.fingerprint() == fp

    def test_bad_private_key_path_degrades_to_none(self, tmp_path) -> None:
        policy = SigningPolicy.from_config(
            {"signing": {"private_key_path": str(tmp_path / "missing.pem")}}
        )
        assert policy.signer is None

    def test_oversized_key_file_read_rejected(self, tmp_path) -> None:
        # The cap must fire before the whole file is read (DoS guard). A valid
        # key is never this large, so pin the read primitive directly.
        from marimo._save.signing_policy import (
            _MAX_KEY_FILE_BYTES,
            _read_key_file,
        )

        big = tmp_path / "big.pem"
        big.write_text("x" * (_MAX_KEY_FILE_BYTES + 1))
        with pytest.raises(OSError, match="too large"):
            _read_key_file(str(big))
        # End-to-end, the read failure degrades to no signer, never a raise.
        policy = SigningPolicy.from_config(
            {"signing": {"private_key_path": str(big)}}
        )
        assert policy.signer is None

    def test_relative_private_key_path_rejected(
        self, keypair, tmp_path, monkeypatch
    ) -> None:
        # A valid key exists at ./key.pem, but a relative path must still be
        # refused — otherwise a project run from its own dir substitutes a key.
        priv, _pub, _fp = keypair
        (tmp_path / "key.pem").write_text(priv)
        monkeypatch.chdir(tmp_path)
        policy = SigningPolicy.from_config(
            {"signing": {"private_key_path": "key.pem"}}
        )
        assert policy.signer is None

    def test_symlinked_key_not_followed(self, keypair, tmp_path) -> None:
        if not hasattr(os, "O_NOFOLLOW"):
            pytest.skip("O_NOFOLLOW unavailable on this platform")
        from marimo._save.signing_policy import _read_key_file

        priv, _pub, _fp = keypair
        real = tmp_path / "real.pem"
        real.write_text(priv)
        link = tmp_path / "link.pem"
        os.symlink(real, link)
        with pytest.raises(OSError):
            _read_key_file(str(link))

    def test_encrypted_pem_degrades_like_garbage(self, tmp_path):
        # An encrypted key raises TypeError (not ValueError) deep in
        # cryptography; it must degrade to None uniformly, not propagate.
        pytest.importorskip("cryptography")
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        enc = Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(b"hunter2"),
        )
        key_file = tmp_path / "enc.pem"
        key_file.write_bytes(enc)
        policy = SigningPolicy.from_config(
            {"signing": {"private_key_path": str(key_file)}}
        )
        assert policy.signer is None

    def test_env_public_key_becomes_trusted_fingerprint(
        self, keypair, monkeypatch
    ) -> None:
        # An inherited public key is a trusted *verifier* (a fingerprint), not
        # an implicitly-trusted own signer.
        _priv, pub, fp = keypair
        monkeypatch.setenv("MARIMO_CACHE_SIGNING_PUBLIC_KEY", pub)
        policy = SigningPolicy.from_config({})
        assert fp in policy.trusted_signers
        assert policy.signer is None

    def test_env_private_key_becomes_signer(
        self, keypair, monkeypatch
    ) -> None:
        priv, _pub, fp = keypair
        monkeypatch.setenv("MARIMO_CACHE_SIGNING_PRIVATE_KEY", priv)
        policy = SigningPolicy.from_config({})
        assert policy.signer is not None
        assert policy.signer.fingerprint() == fp


class TestResolveTrustedSigners:
    def test_none_returns_empty(self) -> None:
        assert _resolve_trusted_signers(None) == set()

    def test_duplicate_after_normalization_kept_once(self) -> None:
        pytest.importorskip("cryptography")
        _priv, pub = generate_keypair()
        fp = fingerprint(pub)
        urlsafe = "SHA256:" + fp[len("SHA256:") :].replace("+", "-").replace(
            "/", "_"
        )
        # Distinct raw keys that canonicalize to the same fingerprint.
        resolved = _resolve_trusted_signers({fp: "a", urlsafe: "b"})
        assert resolved == {fp}


class TestPolicyReachesLoader:
    """The session policy is the loader's default trust/identity source."""

    @pytest.fixture
    def patched_state(self, monkeypatch):
        state = CacheState(store=DEFAULT_STORE())
        monkeypatch.setattr(
            "marimo._save.loaders.lazy._cache_state", lambda: state
        )
        return state

    def test_policy_verification_and_trust_applied(
        self, patched_state, keypair
    ) -> None:
        from marimo._save.loaders.lazy import LazyLoader

        _priv, _pub, fp = keypair
        patched_state.signing_policy = SigningPolicy(
            verification="strict", trusted_signers=frozenset({fp})
        )
        loader = LazyLoader("policy_applied")
        assert loader._verification == "strict"
        assert fp in loader.trusted_signers

    def test_explicit_args_override_policy(
        self, patched_state, keypair
    ) -> None:
        from marimo._save.loaders.lazy import LazyLoader

        _priv, _pub, fp = keypair
        patched_state.signing_policy = SigningPolicy(
            verification="strict", trusted_signers=frozenset({fp})
        )
        # Explicit empty trust + off mode must win over the policy.
        loader = LazyLoader(
            "policy_override", verification="off", trusted_signers=set()
        )
        assert loader._verification == "off"
        assert loader.trusted_signers == frozenset()

    def test_no_policy_uses_defaults(self, patched_state) -> None:
        from marimo._save.loaders.lazy import LazyLoader

        patched_state.signing_policy = None
        loader = LazyLoader("policy_absent", verification="off")
        assert loader._verification == "off"
        assert loader.trusted_signers == frozenset()

    def test_omitted_trusted_signers_inherits_policy(
        self, patched_state, keypair
    ) -> None:
        from marimo._save.loaders.lazy import LazyLoader

        _priv, _pub, fp = keypair
        patched_state.signing_policy = SigningPolicy(
            verification="off", trusted_signers=frozenset({fp})
        )
        loader = LazyLoader("inherits", verification="off")
        assert loader.trusted_signers == frozenset({fp})

    def test_explicit_none_trusted_signers_means_no_trust(
        self, patched_state, keypair
    ) -> None:
        from marimo._save.loaders.lazy import LazyLoader

        _priv, _pub, fp = keypair
        patched_state.signing_policy = SigningPolicy(
            verification="off", trusted_signers=frozenset({fp})
        )
        # Explicit None must NOT silently inherit the policy trust — it means
        # "no trust", like set(). Distinguished from omission by the sentinel.
        loader = LazyLoader(
            "explicit_none", verification="off", trusted_signers=None
        )
        assert loader.trusted_signers == frozenset()
