# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from marimo._save.cache import CacheState
from marimo._save.signing import (
    fingerprint,
    generate_keypair,
)
from marimo._save.signing_policy import (
    SigningPolicy,
    _resolve_trusted_signers,
)
from marimo._save.stores import DEFAULT_STORE
from marimo._session.model import SessionMode


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


def _alternate_spelling(fp: str) -> str:
    """A different raw spelling of `fp` that canonicalizes back to it.

    `normalize_fingerprint` accepts urlsafe base64 and optional padding.
    Padding is the dimension that always differs: base64 of a 32-byte digest is
    43 characters plus one `=`, which `fingerprint()` strips. Swapping `+`/`/`
    for `-`/`_` alone would leave the test vacuous for the ~1 digest in 4 that
    contains neither character.
    """
    body = fp[len("SHA256:") :]
    alternate = "SHA256:" + body.replace("+", "-").replace("/", "_") + "="
    assert alternate != fp
    return alternate


class TestSigningPolicyFromConfig:
    def test_empty_config_defaults(self) -> None:
        policy = SigningPolicy.from_config({})
        assert policy.verification == "on"
        assert policy.trusted_signers == frozenset()
        assert policy.signer is None
        # The machine-key path is frozen at construction, not read live later.
        from marimo._utils.xdg import marimo_state_dir

        assert policy.state_key_path == str(
            marimo_state_dir() / "cache_signing_key.pem"
        )

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
        _priv, _pub, fp = keypair
        # An urlsafe, padded variant must canonicalize to fingerprint() output.
        policy = SigningPolicy.from_config(
            {
                "signing": {
                    "trusted_signers": {_alternate_spelling(fp): "alice"}
                }
            }
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

    def test_non_string_private_key_path_degrades(self) -> None:
        # A wrong type in the TOML must follow the documented fallback, not
        # raise out of policy resolution and stop the session from starting.
        policy = SigningPolicy.from_config(
            {"signing": {"private_key_path": 5}}
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
        # Distinct raw keys that canonicalize to the same fingerprint.
        resolved = _resolve_trusted_signers(
            {fp: "a", _alternate_spelling(fp): "b"}
        )
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


class TestChildContextInheritsPolicy:
    """An embedded app's child context must not resolve a second policy.

    The policy is frozen before the kernel loads any configured `.env`. A child
    context created later would resolve against a post-dotenv environment, so a
    committed `.env` could introduce a signing identity mid-session — the exact
    window freezing is meant to close.
    """

    def _context(self, monkeypatch, *, parent):
        from marimo._runtime.context import kernel_context

        resolved: list[str] = []

        def _spy(*_args: object, **_kwargs: object) -> SigningPolicy:
            resolved.append("called")
            return SigningPolicy(verification="strict")

        # `create_kernel_context` imports these inside the function, so patch
        # them where they are defined.
        monkeypatch.setattr(
            "marimo._save.signing_policy.get_signing_policy", _spy
        )
        monkeypatch.setattr(
            "marimo._save.stores.get_store", lambda _path: DEFAULT_STORE()
        )
        kernel = SimpleNamespace(
            app_metadata=SimpleNamespace(filename=None, app_config=None),
            user_config={},
        )
        ctx = kernel_context.create_kernel_context(
            kernel=kernel,
            streams=SimpleNamespace(stream=None, stdout=None, stderr=None),
            virtual_file_storage=None,
            mode=SessionMode.EDIT,
            parent=parent,
        )
        return ctx, resolved

    def test_root_context_resolves_once(self, monkeypatch) -> None:
        ctx, resolved = self._context(monkeypatch, parent=None)
        assert resolved == ["called"]
        # The resolved policy reaches the cache state, not a default.
        assert ctx.cache.signing_policy is not None
        assert ctx.cache.signing_policy.verification == "strict"

    def test_child_reuses_parent_policy(self, monkeypatch) -> None:
        parent, _ = self._context(monkeypatch, parent=None)
        parent_policy = parent.cache.signing_policy

        child, resolved = self._context(monkeypatch, parent=parent)
        # Not re-resolved: the child holds the very same frozen object.
        assert resolved == []
        assert child.cache.signing_policy is parent_policy


class TestKeyFileReadCap:
    def test_cap_applies_to_bytes_read_not_only_to_stat(
        self, tmp_path, monkeypatch
    ) -> None:
        """The size cap must hold even if the file grows after the stat.

        `_read_key_file` stats the descriptor and then reads from it. A file
        that grows in between would sail past a stat-only check.
        """
        import os as os_module

        from marimo._save.signing_policy import (
            _MAX_KEY_FILE_BYTES,
            _read_key_file,
        )

        big = tmp_path / "grown.pem"
        big.write_text("x" * (_MAX_KEY_FILE_BYTES + 1))

        real_fstat = os_module.fstat

        def _understating_fstat(fd: int) -> object:
            st = real_fstat(fd)
            return SimpleNamespace(st_mode=st.st_mode, st_size=1)

        monkeypatch.setattr(
            "marimo._save.signing_policy.os.fstat", _understating_fstat
        )
        with pytest.raises(OSError, match="too large"):
            _read_key_file(str(big))


class TestInvalidEntriesAreNotLogged:
    def test_entry_is_not_written_to_the_log(self) -> None:
        """The rejected entry must not reach the log.

        A fingerprint gives the reader nothing to act on, and this path runs
        when parsing failed, so what the value holds is unknown — a mispaste
        could put a private key in `trusted_signers`.
        """
        from unittest.mock import patch

        secret = "SHA256:" + "SUPERSECRETKEYMATERIAL" * 4
        with patch("marimo._save.signing_policy.LOGGER") as logger:
            policy = SigningPolicy.from_config(
                {"signing": {"trusted_signers": {secret: "oops"}}}
            )

        assert policy.trusted_signers == frozenset()
        logged = " ".join(str(c) for c in logger.warning.call_args_list)
        assert "SUPERSECRETKEYMATERIAL" not in logged
        # The reader still learns that an entry was dropped, and the format.
        assert "signing.trusted_signers" in logged
        assert "SHA256:<base64>" in logged
