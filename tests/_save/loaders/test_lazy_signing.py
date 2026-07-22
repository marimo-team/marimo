# Copyright 2026 Marimo. All rights reserved.
"""Integration tests for LazyLoader cache signing."""

from __future__ import annotations

import pickle
import tempfile
from pathlib import Path
from typing import Any

import msgspec
import pytest

pytest.importorskip("cryptography", reason="cryptography not installed")

from marimo._save.cache import MARIMO_CACHE_VERSION, Cache
from marimo._save.hash import HashKey
from marimo._save.loaders import LazyLoader
from marimo._save.signing import (
    CacheSignatureError,
    CacheSigner,
    _sha256hex,
    fingerprint,
    generate_keypair,
)
from marimo._save.stores.file import FileStore
from marimo._save.stubs.lazy_stub import (
    Cache as CacheSchema,
    CacheType,
    Item,
    Meta,
)
from tests._save.store.mocks import MockStore


# Module-level class so pickle can resolve it.
class _Point:
    def __init__(self, x: int, y: int) -> None:
        self.x, self.y = x, y


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def key(h: str, cache_type: str = "Pure") -> HashKey:
    return HashKey(h, cache_type)


def _simple_cache(hash_val: str = "abc123", **defs: Any) -> Cache:
    if not defs:
        defs = {"x": 42, "msg": "hello"}
    return Cache(
        defs=defs,
        hash=hash_val,
        cache_type="Pure",
        stateful_refs=set(),
        hit=False,
        meta={"version": MARIMO_CACHE_VERSION},
    )


def _keypair() -> tuple[CacheSigner, CacheSigner]:
    """Return (full_signer_with_private, verifier_with_public_only)."""
    private_pem, public_pem = generate_keypair()
    return (
        CacheSigner.from_private_key_pem(private_pem),
        CacheSigner.from_public_key_pem(public_pem),
    )


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


class _FileStoreLoaderTest:
    """Shared scaffolding: a temp-dir FileStore and a loader factory over it."""

    def setup_method(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = FileStore(save_path=self.temp_dir.name)

    def teardown_method(self) -> None:
        self.temp_dir.cleanup()

    def _loader(self, **kwargs: Any) -> LazyLoader:
        return LazyLoader("test", store=self.store, **kwargs)


class TestSignedRoundTrip(_FileStoreLoaderTest):
    def test_signer_and_mode_settable_via_setattr(self) -> None:
        """Reconfiguring via setattr (as LoaderPartial.create_or_reconfigure
        does) works for signer and mode."""
        signer, verifier = _keypair()
        # Start in off mode with no signer, then reconfigure to a signing
        # loader — mirroring how create_or_reconfigure applies kwargs.
        loader = self._loader(signer=None, mode="off")
        assert loader.signer is None
        assert loader.mode == "off"

        loader.signer = signer
        loader.mode = "verify"
        assert loader._signer is signer
        assert loader._mode == "verify"

        # Full round-trip with the reconfigured signer
        cache = _simple_cache(hash_val="reconfig_hash", v=99)
        assert loader.save_cache(cache)
        loader.flush()

        reader = self._loader(signer=verifier)
        loaded = reader.load_cache(key("reconfig_hash"))
        assert loaded is not None
        assert loaded.defs["v"] == 99

    def test_reconfigure_unset_signer_does_not_automint_for_shared_store(
        self,
    ) -> None:
        """Re-setting the signer to unset on a non-local (shared) store must
        not auto-generate a machine-local key when the deferred resolution
        fires — only explicit/env keys apply, matching __init__'s
        local-vs-shared distinction. The setter stores the sentinel unresolved;
        resolution happens lazily on the first `signer` property access."""
        from unittest import mock

        from marimo._save.loaders.lazy import _SIGNER_UNSET

        loader = LazyLoader(
            "ns", store=MockStore(), signer=None, mode="verify"
        )
        with mock.patch(
            "marimo._save.loaders.lazy._get_default_signer"
        ) as gds:
            gds.return_value = None
            loader.signer = _SIGNER_UNSET
            # Setter defers: nothing resolved yet.
            gds.assert_not_called()
            # Property access (non-off mode) triggers the single resolution.
            _ = loader.signer
            gds.assert_called_once()
            assert gds.call_args.kwargs.get("auto_generate") is False

    def test_default_round_trip(self) -> None:
        """The default loader auto-resolves a local signing key, so a plain
        save/load round-trips (signs on write, verifies own key on read)."""
        loader = self._loader()
        cache = _simple_cache()
        assert loader.save_cache(cache)
        loader.flush()

        loaded = loader.load_cache(key("abc123"))
        assert loaded is not None
        assert loaded.defs["x"] == 42
        assert loaded.defs["msg"] == "hello"

    def test_signed_round_trip(self) -> None:
        """Full signer → save signs, load with public key verifies (a loader
        trusts its own key's fingerprint, so no trusted_signers needed)."""
        signer, verifier = _keypair()

        writer = self._loader(signer=signer)
        cache = _simple_cache(hash_val="signed_hash", x=99, label="signed")
        assert writer.save_cache(cache)
        writer.flush()

        reader = self._loader(signer=verifier)
        loaded = reader.load_cache(key("signed_hash"))
        assert loaded is not None
        assert loaded.defs["x"] == 99
        assert loaded.defs["label"] == "signed"

    def test_signed_round_trip_with_pickle_object(self) -> None:
        """Pickle blobs are hash-verified before deserialization."""
        signer, verifier = _keypair()

        pt = _Point(3, 4)
        writer = self._loader(signer=signer)
        cache = _simple_cache(hash_val="pt_hash", pt=pt)
        assert writer.save_cache(cache)
        writer.flush()

        reader = self._loader(signer=verifier)
        loaded = reader.load_cache(key("pt_hash"))
        assert loaded is not None
        result = loaded.defs["pt"]
        assert result.x == 3
        assert result.y == 4

    def test_self_verify_with_private_key(self) -> None:
        """A loader with a private-key signer can also verify its own entries."""
        signer, _ = _keypair()
        loader = self._loader(signer=signer)

        cache = _simple_cache(hash_val="self_verify", val=7)
        assert loader.save_cache(cache)
        loader.flush()

        loaded = loader.load_cache(key("self_verify"))
        assert loaded is not None
        assert loaded.defs["val"] == 7

    def test_trusted_third_party_direct_signer(self) -> None:
        """A reader trusts a third party's direct signature by adding the
        writer's fingerprint to trusted_signers (reader has no own key)."""
        signer, verifier = _keypair()
        writer = self._loader(signer=signer)
        writer.save_cache(_simple_cache(hash_val="third_party", n=5))
        writer.flush()

        reader = self._loader(
            signer=None, trusted_signers={verifier.fingerprint()}
        )
        loaded = reader.load_cache(key("third_party"))
        assert loaded is not None
        assert loaded.defs["n"] == 5

    def test_mock_store_signed_round_trip(self) -> None:
        """Works with any Store backend (MockStore here)."""
        signer, verifier = _keypair()
        store = MockStore()

        writer = LazyLoader("ns", store=store, signer=signer)
        cache = _simple_cache(hash_val="mock_hash", n=123)
        assert writer.save_cache(cache)
        writer.flush()

        reader = LazyLoader("ns", store=store, signer=verifier)
        loaded = reader.load_cache(key("mock_hash"))
        assert loaded is not None
        assert loaded.defs["n"] == 123


# ---------------------------------------------------------------------------
# Unsigned-entry behavior (mode-governed)
# ---------------------------------------------------------------------------


class TestUnsignedEntries(_FileStoreLoaderTest):
    def _write_unsigned(self, hash_val: str = "unsigned_hash") -> None:
        """Write a valid but unsigned cache entry via an off-mode loader
        (off is the only mode that writes unsigned)."""
        loader = self._loader(signer=None, mode="off")
        cache = _simple_cache(hash_val=hash_val, z=55)
        assert loader.save_cache(cache)
        loader.flush()

    def test_unsigned_served_in_off_mode(self) -> None:
        """off mode neither signs nor verifies: unsigned entries load fine."""
        self._write_unsigned()
        loader = self._loader(signer=None, mode="off")
        loaded = loader.load_cache(key("unsigned_hash"))
        assert loaded is not None
        assert loaded.defs["z"] == 55

    def test_unsigned_misses_in_verify_mode(self) -> None:
        """verify mode (default): an unsigned entry is unverifiable, so it
        misses (fail-safe) rather than being served."""
        self._write_unsigned()
        _, verifier = _keypair()
        loader = self._loader(signer=verifier)  # mode="verify" default
        assert loader.load_cache(key("unsigned_hash")) is None

    def test_unsigned_rejected_in_strict_mode(self) -> None:
        """strict mode: unsigned entries raise CacheSignatureError."""
        self._write_unsigned()
        _, verifier = _keypair()
        loader = self._loader(signer=verifier, mode="strict")
        with pytest.raises(CacheSignatureError, match="unsigned"):
            loader.load_cache(key("unsigned_hash"))

    def test_verify_only_signer_write_is_skipped_and_warns(self) -> None:
        """A verify-only signer (no private key) in verify mode cannot sign, so
        the write is skipped (no unsigned entry written) and a warning logged."""
        from unittest.mock import patch

        _, verifier = _keypair()
        loader = self._loader(signer=verifier)  # verify mode, no private key
        cache = _simple_cache(hash_val="warn_hash", z=1)
        with patch("marimo._save.loaders.lazy.LOGGER") as mock_log:
            assert loader.save_cache(cache) is False
            loader.flush()
        warning_msgs = [str(call) for call in mock_log.warning.call_args_list]
        assert any("cannot sign" in msg.lower() for msg in warning_msgs)
        # Nothing was written.
        assert self.store.get(str(loader.build_path(key("warn_hash")))) is None


# ---------------------------------------------------------------------------
# Tampering tests
# ---------------------------------------------------------------------------


class TestTampering(_FileStoreLoaderTest):
    def _write_signed(
        self, hash_val: str = "tamper_hash", **defs: Any
    ) -> CacheSigner:
        if not defs:
            defs = {"v": 1}
        signer, _ = _keypair()
        loader = LazyLoader("test", store=self.store, signer=signer)
        cache = _simple_cache(hash_val=hash_val, **defs)
        loader.save_cache(cache)
        loader.flush()
        return signer

    def _read_loader(self, signer: CacheSigner, **kwargs: Any) -> LazyLoader:
        # Build a verifier from the same public key
        verifier = CacheSigner.from_public_key_pem(signer.public_key_pem())
        return LazyLoader("test", store=self.store, signer=verifier, **kwargs)

    def test_tampered_manifest_raises(self) -> None:
        """Flipping a byte in the manifest invalidates the Ed25519 signature.
        In strict mode this raises rather than degrading to miss."""
        signer = self._write_signed(hash_val="manip_manifest")

        # Locate and corrupt the manifest file
        manifest_key = str(
            LazyLoader("test", store=self.store, mode="off").build_path(
                key("manip_manifest")
            )
        )
        raw = self.store.get(manifest_key)
        assert raw is not None
        # Decode, mutate, re-encode without updating the signature
        schema = msgspec.json.decode(raw, type=CacheSchema)
        tampered_meta = msgspec.structs.replace(schema.meta, version=9999)
        tampered = msgspec.json.encode(
            msgspec.structs.replace(schema, meta=tampered_meta)
        )
        self.store.put(manifest_key, tampered)

        reader = self._read_loader(signer, mode="strict")
        with pytest.raises(CacheSignatureError):
            reader.load_cache(key("manip_manifest"))

    def test_tampered_blob_raises_before_unpickling(self) -> None:
        """A replaced blob raises CacheSignatureError before pickle.loads."""
        signer = self._write_signed(
            hash_val="blob_tamper", secret={"key": "val"}
        )

        # Find the pickle blob and overwrite it with a different payload
        blob_dir = Path(self.temp_dir.name) / "test" / "blob_tamper"
        blobs = list(blob_dir.glob("*.pickle"))
        assert blobs, "expected a .pickle blob"
        evil_bytes = pickle.dumps({"injected": True})
        blobs[0].write_bytes(evil_bytes)

        reader = self._read_loader(signer, mode="strict")
        with pytest.raises(CacheSignatureError, match="checksum"):
            reader.load_cache(key("blob_tamper"))

    def test_signature_error_not_swallowed_by_load_cache(self) -> None:
        """load_cache re-raises CacheSignatureError in strict mode."""
        signer = self._write_signed(hash_val="sig_swallow")

        manifest_key = str(
            LazyLoader("test", store=self.store, mode="off").build_path(
                key("sig_swallow")
            )
        )
        raw = self.store.get(manifest_key)
        assert raw is not None
        schema = msgspec.json.decode(raw, type=CacheSchema)
        tampered_meta = msgspec.structs.replace(schema.meta, version=0)
        tampered = msgspec.json.encode(
            msgspec.structs.replace(schema, meta=tampered_meta)
        )
        self.store.put(manifest_key, tampered)

        reader = self._read_loader(signer, mode="strict")
        # Must raise, not return None
        with pytest.raises(CacheSignatureError):
            reader.load_cache(key("sig_swallow"))

    def test_bad_signature_degrades_to_miss_in_verify_mode(self) -> None:
        """In verify mode a tampered manifest returns None (cache miss)."""
        signer = self._write_signed(hash_val="verify_tamper")

        manifest_key = str(
            LazyLoader("test", store=self.store, mode="off").build_path(
                key("verify_tamper")
            )
        )
        raw = self.store.get(manifest_key)
        assert raw is not None
        schema = msgspec.json.decode(raw, type=CacheSchema)
        tampered_meta = msgspec.structs.replace(schema.meta, version=9999)
        tampered = msgspec.json.encode(
            msgspec.structs.replace(schema, meta=tampered_meta)
        )
        self.store.put(manifest_key, tampered)

        # verify mode (default) — degrade to cache miss
        reader = self._read_loader(signer)
        assert reader.load_cache(key("verify_tamper")) is None

    def test_wrong_key_cannot_verify(self) -> None:
        """An entry signed by key A cannot be verified by key B."""
        signer_a, _ = _keypair()
        _, verifier_b = _keypair()

        writer = LazyLoader("test", store=self.store, signer=signer_a)
        cache = _simple_cache(hash_val="wrong_key", val=1)
        writer.save_cache(cache)
        writer.flush()

        reader = LazyLoader(
            "test", store=self.store, signer=verifier_b, mode="strict"
        )
        with pytest.raises(CacheSignatureError):
            reader.load_cache(key("wrong_key"))

    def test_foreign_key_misses_in_verify_mode(self) -> None:
        """A different key's signature does not verify against this loader's
        key, so the entry misses (recomputes) rather than being served
        unverified — even in verify mode. Sharing a cache across machines
        requires a shared/trusted key, not silent acceptance."""
        signer_a, _ = _keypair()
        _, verifier_b = _keypair()

        writer = LazyLoader("test", store=self.store, signer=signer_a)
        writer.save_cache(_simple_cache(hash_val="foreign_ok", val=7))
        writer.flush()

        # verify mode (default) with an unrelated key B: the foreign signature
        # fails verification -> fail-safe cache miss.
        reader = LazyLoader("test", store=self.store, signer=verifier_b)
        assert reader.load_cache(key("foreign_ok")) is None

    def test_signed_manifest_missing_blob_hash_rejected(self) -> None:
        """A validly-signed manifest that omits the integrity hash for a blob
        it references is rejected (writer-drift / integrity-bypass guard),
        rather than letting the blob reach pickle.loads unverified."""
        from marimo._save.loaders.lazy import _signable_bytes

        signer = self._write_signed(hash_val="missing_hash", secret={"k": "v"})
        manifest_key = str(
            LazyLoader("test", store=self.store, mode="off").build_path(
                key("missing_hash")
            )
        )
        raw = self.store.get(manifest_key)
        assert raw is not None
        schema = msgspec.json.decode(raw, type=CacheSchema)
        # Drop one referenced blob's hash, then re-sign so the manifest
        # signature itself remains valid (the attack we guard against is a
        # signed-but-hash-incomplete manifest, not a broken signature).
        blob_key = next(iter(schema.meta.blob_hashes))
        pruned = {
            k: v for k, v in schema.meta.blob_hashes.items() if k != blob_key
        }
        base_meta = msgspec.structs.replace(
            schema.meta, blob_hashes=pruned, signature=None
        )
        base = msgspec.structs.replace(schema, meta=base_meta)
        sig = signer.sign(_signable_bytes(base))
        resigned = msgspec.json.encode(
            msgspec.structs.replace(
                base, meta=msgspec.structs.replace(base_meta, signature=sig)
            )
        )
        self.store.put(manifest_key, resigned)

        reader = self._read_loader(signer, mode="strict")
        with pytest.raises(CacheSignatureError, match="integrity hash"):
            reader.load_cache(key("missing_hash"))

    def test_manifest_hash_mismatch_misses_before_blob_io(self) -> None:
        """A manifest whose internal hash disagrees with its store path is a
        corrupt/misfiled entry: miss before fetching any blob (otherwise the
        mismatch is only caught after every blob is pickle.loads()-ed)."""
        loader = LazyLoader("test", store=self.store, mode="off")
        ref = (Path("test") / "wrong" / "v.pickle").as_posix()
        manifest = msgspec.json.encode(
            CacheSchema(
                hash="different_hash",
                cache_type=CacheType.PURE,
                defs={"v": Item(reference=ref)},
                stateful_refs=[],
                meta=Meta(version=MARIMO_CACHE_VERSION),
            )
        )
        self.store.put(str(loader.build_path(key("asked_hash"))), manifest)

        fetched: list[str] = []
        orig = self.store.get

        def spy(k: str) -> Any:
            fetched.append(k)
            return orig(k)

        self.store.get = spy  # type: ignore[method-assign]
        try:
            assert loader.load_cache(key("asked_hash")) is None
        finally:
            self.store.get = orig  # type: ignore[method-assign]
        assert ref not in fetched


# ---------------------------------------------------------------------------
# Blob-hash content in manifest
# ---------------------------------------------------------------------------


class TestBlobHashesInManifest(_FileStoreLoaderTest):
    def test_unsigned_manifest_has_empty_blob_hashes(self) -> None:
        loader = LazyLoader("test", store=self.store, signer=None, mode="off")
        cache = _simple_cache(hash_val="no_hashes", x=1)
        loader.save_cache(cache)
        loader.flush()

        manifest_key = str(loader.build_path(key("no_hashes")))
        raw = self.store.get(manifest_key)
        schema = msgspec.json.decode(raw, type=CacheSchema)
        assert schema.meta.blob_hashes == {}
        assert schema.meta.signature is None
        assert schema.meta.signer_public_key is None

    def test_signed_manifest_has_blob_hashes_and_signature(self) -> None:
        signer, _ = _keypair()
        loader = LazyLoader("test", store=self.store, signer=signer)
        cache = _simple_cache(hash_val="with_hashes", obj={"a": 1})
        loader.save_cache(cache)
        loader.flush()

        manifest_key = str(loader.build_path(key("with_hashes")))
        raw = self.store.get(manifest_key)
        schema = msgspec.json.decode(raw, type=CacheSchema)
        # Blob hashes should be populated
        assert len(schema.meta.blob_hashes) > 0
        # Each value is a 64-char hex string
        for h in schema.meta.blob_hashes.values():
            assert len(h) == 64
        # Signature and public key present
        assert schema.meta.signature is not None
        assert schema.meta.signer_public_key is not None
        assert "PUBLIC KEY" in schema.meta.signer_public_key

    def test_blob_hashes_match_actual_blobs(self) -> None:
        signer, _ = _keypair()
        loader = LazyLoader("test", store=self.store, signer=signer)
        cache = _simple_cache(hash_val="verify_hash_content", n=42)
        loader.save_cache(cache)
        loader.flush()

        manifest_key = str(loader.build_path(key("verify_hash_content")))
        raw = self.store.get(manifest_key)
        schema = msgspec.json.decode(raw, type=CacheSchema)

        for blob_key, expected_hex in schema.meta.blob_hashes.items():
            blob_data = self.store.get(blob_key)
            assert blob_data is not None
            assert _sha256hex(blob_data) == expected_hex


# ---------------------------------------------------------------------------
# Signable bytes stability (regression test)
# ---------------------------------------------------------------------------


class TestSignableBytesStability:
    """_signable_bytes must produce identical output across runs for the same
    schema.  If msgspec changes field ordering or encoding, signatures written
    by one version become unverifiable by another."""

    def test_signable_bytes_strips_signature(self) -> None:
        """The signature envelope field is cleared regardless of its value."""
        from marimo._save.loaders.lazy import _signable_bytes

        meta = Meta(
            version=1,
            blob_hashes={"k": "a" * 64},
            signature="should_be_stripped",
        )
        schema = CacheSchema(
            hash="h",
            cache_type=CacheType.PURE,
            defs={},
            stateful_refs=[],
            meta=meta,
        )
        from marimo._save.loaders.lazy import _MANIFEST_SIG_CONTEXT

        out = _signable_bytes(schema)
        # Signable bytes carry a domain-separation prefix before the JSON.
        assert out.startswith(_MANIFEST_SIG_CONTEXT)
        decoded = msgspec.json.decode(
            out[len(_MANIFEST_SIG_CONTEXT) :], type=CacheSchema
        )
        assert decoded.meta.signature is None
        # Non-envelope fields preserved
        assert decoded.meta.blob_hashes == {"k": "a" * 64}
        assert decoded.meta.version == 1

    def test_signable_bytes_deterministic(self) -> None:
        """Same input always produces identical bytes."""
        from marimo._save.loaders.lazy import _signable_bytes

        meta = Meta(version=1, blob_hashes={"x": "b" * 64})
        schema = CacheSchema(
            hash="det",
            cache_type=CacheType.PURE,
            defs={},
            stateful_refs=[],
            meta=meta,
        )
        assert _signable_bytes(schema) == _signable_bytes(schema)


# ---------------------------------------------------------------------------
# Mode + capability validation
# ---------------------------------------------------------------------------


class TestModeAndCapabilityValidation(_FileStoreLoaderTest):
    def test_strict_with_no_capability_raises(self) -> None:
        """strict + signer=None + no trusted_signers → ValueError at init."""
        with pytest.raises(ValueError, match="strict"):
            LazyLoader("test", store=self.store, signer=None, mode="strict")

    def test_strict_with_signer_is_fine(self) -> None:
        _, verifier = generate_keypair()
        signer = CacheSigner.from_public_key_pem(verifier)
        loader = LazyLoader(
            "test", store=self.store, signer=signer, mode="strict"
        )
        assert loader.mode == "strict"

    def test_strict_with_trusted_signers_only_is_fine(self) -> None:
        _, root_pub = generate_keypair()
        loader = LazyLoader(
            "test",
            store=self.store,
            signer=None,
            trusted_signers={fingerprint(root_pub)},
            mode="strict",
        )
        assert loader.mode == "strict"

    def test_verify_with_no_capability_degrades_to_off(self) -> None:
        """verify + nothing to verify with → degrade to off (no raise); an
        unsigned entry is then served."""
        # Write an unsigned entry.
        w = LazyLoader("test", store=self.store, signer=None, mode="off")
        w.save_cache(_simple_cache(hash_val="degrade", z=3))
        w.flush()
        # Reader with verify but no signer and no trusted_signers degrades.
        reader = LazyLoader("test", store=self.store, signer=None)
        loaded = reader.load_cache(key("degrade"))
        assert loaded is not None
        assert loaded.defs["z"] == 3

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cache signing mode"):
            LazyLoader("test", store=self.store, mode="paranoid")

    def test_bare_string_trusted_signers_raises(self) -> None:
        """A bare str would iterate into single characters — rejected."""
        with pytest.raises(TypeError, match="iterable of fingerprint"):
            LazyLoader(
                "test",
                store=self.store,
                trusted_signers="SHA256:abc",  # type: ignore[arg-type]
            )

    def test_malformed_fingerprint_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid trusted_signers"):
            LazyLoader("test", store=self.store, trusted_signers={"not-a-fp"})

    def test_bad_signer_type_raises(self) -> None:
        with pytest.raises(TypeError, match="signer must be a CacheSigner"):
            LazyLoader("test", store=self.store, signer="nope")  # type: ignore[arg-type]

    def test_no_cryptography_strict_raises(self) -> None:
        """strict must fail closed when cryptography is unavailable."""
        from unittest import mock

        signer, _ = _keypair()
        with mock.patch(
            "marimo._dependencies.dependencies.DependencyManager."
            "cryptography.has",
            return_value=False,
        ):
            with pytest.raises(ValueError, match="cryptography"):
                LazyLoader(
                    "test", store=self.store, signer=signer, mode="strict"
                )

    def test_no_cryptography_verify_degrades_to_off(self) -> None:
        """verify degrades to off (serves unsigned) when cryptography is
        unavailable — unsigned caching still works without the package."""
        from unittest import mock

        # Write an unsigned entry (off mode).
        w = LazyLoader("test", store=self.store, signer=None, mode="off")
        w.save_cache(_simple_cache(hash_val="nocrypto", z=8))
        w.flush()

        signer, _ = _keypair()
        with mock.patch(
            "marimo._dependencies.dependencies.DependencyManager."
            "cryptography.has",
            return_value=False,
        ):
            reader = LazyLoader("test", store=self.store, signer=signer)
            assert reader._effective_mode() == "off"
            loaded = reader.load_cache(key("nocrypto"))
        assert loaded is not None
        assert loaded.defs["z"] == 8


# ---------------------------------------------------------------------------
# Review fixes: trust/sign composition, remote posture, strict hash guard,
# fingerprint normalization, frozen trust set
# ---------------------------------------------------------------------------


class TestReviewFixes(_FileStoreLoaderTest):
    def test_trusted_signers_still_signs_own_writes_on_local_store(
        self,
    ) -> None:
        """Configuring trusted_signers must not turn off signing of our own
        writes on a local store: trust composes with signing (a loader that
        also trusts a teammate keeps its auto-resolved key and round-trips its
        own cache)."""
        _, other_pub = generate_keypair()
        loader = LazyLoader(
            "test",
            store=self.store,
            trusted_signers={fingerprint(other_pub)},
        )
        # Own signing key auto-resolved despite trusted_signers being set.
        assert loader.signer is not None
        assert loader.save_cache(_simple_cache(hash_val="compose", k=1))
        loader.flush()
        loaded = loader.load_cache(key("compose"))
        assert loaded is not None
        assert loaded.defs["k"] == 1

    def test_remote_store_verify_does_not_degrade_to_off(self) -> None:
        """On a shared/remote store, verify with no signer/trusted must NOT
        degrade to off (which would serve unverified bytes from exactly the
        backend signing protects); it stays verify, so an unsigned entry
        misses."""
        store = MockStore()
        w = LazyLoader("ns", store=store, signer=None, mode="off")
        w.save_cache(_simple_cache(hash_val="remote_unsigned", z=3))
        w.flush()

        reader = LazyLoader("ns", store=store, signer=None)
        assert reader._effective_mode() == "verify"
        assert reader.load_cache(key("remote_unsigned")) is None

    def test_local_store_verify_still_degrades_to_off(self) -> None:
        """A local file store keeps the benign degrade-to-off when there is
        nothing to verify with (low-threat, single-machine)."""
        w = LazyLoader("test", store=self.store, signer=None, mode="off")
        w.save_cache(_simple_cache(hash_val="local_unsigned", z=4))
        w.flush()
        reader = LazyLoader("test", store=self.store, signer=None)
        assert reader._effective_mode() == "off"
        loaded = reader.load_cache(key("local_unsigned"))
        assert loaded is not None
        assert loaded.defs["z"] == 4

    def test_strict_hash_mismatch_raises(self) -> None:
        """Under strict, a manifest whose internal hash disagrees with its
        store path is a trust anomaly and must raise (fail-closed), not miss."""
        signer, _ = _keypair()
        loader = LazyLoader(
            "test", store=self.store, signer=signer, mode="strict"
        )
        manifest = msgspec.json.encode(
            CacheSchema(
                hash="different_hash",
                cache_type=CacheType.PURE,
                defs={},
                stateful_refs=[],
                meta=Meta(version=MARIMO_CACHE_VERSION),
            )
        )
        self.store.put(str(loader.build_path(key("asked_hash"))), manifest)
        with pytest.raises(CacheSignatureError, match="does not match"):
            loader.load_cache(key("asked_hash"))

    def test_fingerprint_normalization_accepts_padded_and_urlsafe(
        self,
    ) -> None:
        """A padded or urlsafe fingerprint paste is canonicalized so it still
        matches fingerprint() output (rather than validating but never
        matching → permanent silent miss)."""
        signer, _ = _keypair()
        writer = LazyLoader("test", store=self.store, signer=signer)
        writer.save_cache(_simple_cache(hash_val="norm", n=5))
        writer.flush()

        canonical = signer.fingerprint()
        body = canonical[len("SHA256:") :]
        padded = "SHA256:" + body + "=" * (-len(body) % 4)
        urlsafe = "SHA256:" + body.replace("+", "-").replace("/", "_")

        for variant in (padded, urlsafe):
            reader = LazyLoader(
                "test",
                store=self.store,
                signer=None,
                trusted_signers={variant},
            )
            assert reader.trusted_signers == {canonical}
            loaded = reader.load_cache(key("norm"))
            assert loaded is not None
            assert loaded.defs["n"] == 5

    def test_trusted_signers_property_is_frozen_copy(self) -> None:
        """The property returns a frozenset copy so mutating it cannot bypass
        _normalize_fingerprints."""
        _, pub = generate_keypair()
        loader = LazyLoader(
            "test",
            store=self.store,
            signer=None,
            trusted_signers={fingerprint(pub)},
            mode="off",
        )
        ts = loader.trusted_signers
        assert isinstance(ts, frozenset)
        assert not hasattr(ts, "add")

    def test_no_crypto_remote_store_stays_verify(self) -> None:
        """Without cryptography, a shared/remote store must NOT degrade to off
        (which would deserialize unverified bytes from the very backend signing
        protects); it stays verify so an unsigned entry misses."""
        from unittest import mock

        store = MockStore()
        w = LazyLoader("ns", store=store, signer=None, mode="off")
        w.save_cache(_simple_cache(hash_val="nocrypto_remote", z=9))
        w.flush()

        with mock.patch(
            "marimo._dependencies.dependencies.DependencyManager."
            "cryptography.has",
            return_value=False,
        ):
            reader = LazyLoader("ns", store=store, signer=None)
            assert reader._effective_mode() == "verify"
            assert reader.load_cache(key("nocrypto_remote")) is None

    def test_non_finite_floats_round_trip_and_keep_signature(self) -> None:
        """nan/inf/-inf can't be inlined via `primitive` (msgspec encodes them
        as JSON null, which corrupts the value and breaks the signature once
        re-encoded). They round-trip through a compact inline `special_float`
        token — no pickle blob — and survive a strict round-trip."""
        import math

        signer, verifier = _keypair()
        writer = LazyLoader(
            "test", store=self.store, signer=signer, mode="verify"
        )
        writer.save_cache(
            _simple_cache(
                hash_val="nonfinite",
                a=float("nan"),
                b=float("inf"),
                c=float("-inf"),
                d=1.5,
            )
        )
        writer.flush()

        # No pickle blob is written for the non-finite values — they live
        # inline in the manifest as tokens.
        manifest = msgspec.json.decode(
            self.store.get(str(writer.build_path(key("nonfinite")))),
            type=CacheSchema,
        )
        assert manifest.defs["a"].special_float == "nan"
        assert manifest.defs["b"].special_float == "inf"
        assert manifest.defs["c"].special_float == "-inf"
        assert manifest.defs["d"].primitive == 1.5

        # strict → load returns a value only if verification passes; a broken
        # signature would raise instead.
        reader = LazyLoader(
            "test", store=self.store, signer=verifier, mode="strict"
        )
        loaded = reader.load_cache(key("nonfinite"))
        assert loaded is not None
        assert math.isnan(loaded.defs["a"])
        assert loaded.defs["b"] == float("inf")
        assert loaded.defs["c"] == float("-inf")
        assert loaded.defs["d"] == 1.5

    def test_fingerprint_slack_bits_canonicalized(self) -> None:
        """base64 of a 32-byte digest has 2 slack bits in its final char, so
        several final chars decode to the same digest. Normalization must
        re-encode to the canonical form (not echo the pasted char), else a
        slack-bit variant validates but never matches → permanent silent miss."""
        import base64
        import string

        from marimo._save.loaders.lazy import _normalize_fingerprint

        signer, _ = _keypair()
        canonical = signer.fingerprint()
        body = canonical[len("SHA256:") :]
        raw = base64.b64decode(body + "=" * (-len(body) % 4))
        alphabet = (
            string.ascii_uppercase
            + string.ascii_lowercase
            + string.digits
            + "+/"
        )
        variant_char = next(
            c
            for c in alphabet
            if c != body[-1]
            and base64.b64decode(body[:-1] + c + "=", validate=True) == raw
        )
        variant = "SHA256:" + body[:-1] + variant_char
        assert variant != canonical
        assert _normalize_fingerprint(variant) == canonical

    def test_strict_raises_on_unsupported_declared_key(self) -> None:
        """If parsing the manifest's declared key raises (e.g. cryptography's
        UnsupportedAlgorithm, which is not a ValueError), a strict loader must
        still raise 'unverifiable' rather than letting it escape to a silent
        miss."""
        from unittest import mock

        from cryptography.exceptions import UnsupportedAlgorithm

        signer, verifier = _keypair()
        writer = LazyLoader(
            "test", store=self.store, signer=signer, mode="verify"
        )
        writer.save_cache(_simple_cache(hash_val="unsupported", z=1))
        writer.flush()

        # Reader trusts the declared key by fingerprint but has no own key, so
        # the declared-key path is the only route to verification.
        reader = LazyLoader(
            "test",
            store=self.store,
            signer=None,
            trusted_signers={signer.fingerprint()},
            mode="strict",
        )
        with mock.patch(
            "marimo._save.loaders.lazy.fingerprint",
            side_effect=UnsupportedAlgorithm("bad OID"),
        ):
            with pytest.raises(CacheSignatureError):
                reader.load_cache(key("unsupported"))

    def test_off_mode_does_not_resolve_or_mint_signer(self) -> None:
        """mode='off' never signs or verifies, so it must not load or mint a
        machine-local signing key (avoiding a stray key file / read-only
        state-dir warnings for a caller who opted out)."""
        from unittest import mock

        from marimo._save.loaders.lazy import _Unset

        with mock.patch(
            "marimo._save.loaders.lazy._get_default_signer"
        ) as get_signer:
            loader = LazyLoader("test", store=self.store, mode="off")
            assert loader.signer is None
            loader.save_cache(_simple_cache(hash_val="offkey", z=1))
            loader.flush()
            get_signer.assert_not_called()
            # Still unresolved, so a later reconfigure to verify can resolve.
            assert isinstance(loader._signer, _Unset)

    def test_wasm_store_verify_degrades_to_off(self) -> None:
        """The WASM HTTP store is same-origin as the notebook code, so a verify
        loader with no key/anchor degrades to off (serves) rather than missing
        every read — otherwise the bundled-cache restore feature this stack
        ships is silently disabled in the browser."""
        from marimo._save.loaders.lazy import WasmLazyStore
        from marimo._save.stores.dict_store import DictStore

        store = WasmLazyStore(DictStore())
        w = LazyLoader("ns", store=store, signer=None, mode="off")
        assert w.save_cache(_simple_cache(hash_val="wasm_unsigned", z=7))
        w.flush()

        reader = LazyLoader("ns", store=store, signer=None, mode="verify")
        assert reader._effective_mode() == "off"
        loaded = reader.load_cache(key("wasm_unsigned"))
        assert loaded is not None
        assert loaded.defs["z"] == 7

    def test_wasm_store_no_crypto_degrades_to_off(self) -> None:
        """Same same-origin rationale under the no-cryptography branch: the
        WASM store degrades to off rather than missing every read."""
        from unittest import mock

        from marimo._save.loaders.lazy import WasmLazyStore
        from marimo._save.stores.dict_store import DictStore

        store = WasmLazyStore(DictStore())
        w = LazyLoader("ns", store=store, signer=None, mode="off")
        w.save_cache(_simple_cache(hash_val="wasm_nocrypto", z=8))
        w.flush()

        with mock.patch(
            "marimo._dependencies.dependencies.DependencyManager."
            "cryptography.has",
            return_value=False,
        ):
            reader = LazyLoader("ns", store=store, signer=None, mode="verify")
            assert reader._effective_mode() == "off"
            loaded = reader.load_cache(key("wasm_nocrypto"))
            assert loaded is not None
            assert loaded.defs["z"] == 8

    def test_strict_raises_on_undecodable_manifest(self) -> None:
        """A manifest that fails to decode (malformed JSON, or a tampered
        one-of Item) is a trust anomaly under strict and must raise
        (fail-closed), not fall through to a silent generic miss. verify
        (fail-safe) treats the same garbage as a plain miss."""
        signer, _ = _keypair()
        loader = LazyLoader(
            "test", store=self.store, signer=signer, mode="strict"
        )
        path = str(loader.build_path(key("garbage")))
        self.store.put(path, b"{ this is not valid json")
        with pytest.raises(CacheSignatureError):
            loader.load_cache(key("garbage"))

        verify_loader = LazyLoader(
            "test", store=self.store, signer=signer, mode="verify"
        )
        assert verify_loader.load_cache(key("garbage")) is None

    def test_bytes_forced_inline_falls_through_to_blob_reference(self) -> None:
        """to_item must never inline bytes via `primitive` (msgspec base64s it
        to a str, silently corrupting the value). Even when inline is forced,
        bytes fall through to a blob reference instead."""
        from pathlib import Path

        from marimo._save.loaders.lazy import to_item

        item = to_item(
            Path("ns/h"),
            b"\x00\x01raw",
            var_name="b",
            loader="inline",
            hash="h",
        )
        assert item.primitive is None
        assert item.reference == "ns/h/b.pickle"

    def test_strict_missing_blob_under_verified_manifest_raises(self) -> None:
        """A verified manifest whose blob is gone is an integrity failure:
        strict raises (fail-closed), verify misses (recompute). Otherwise a
        strict loader would silently miss an incomplete signed entry."""
        signer, verifier = _keypair()
        writer = self._loader(signer=signer)
        writer.save_cache(
            _simple_cache(hash_val="missing_blob", pt=_Point(1, 2))
        )
        writer.flush()
        # Drop the blob but leave the (still validly-signed) manifest.
        assert self.store.clear("test/missing_blob/pt.pickle")

        strict = self._loader(signer=verifier, mode="strict")
        with pytest.raises(CacheSignatureError):
            strict.load_cache(key("missing_blob"))

        verify = self._loader(signer=verifier, mode="verify")
        assert verify.load_cache(key("missing_blob")) is None

    def test_strict_deserialize_failure_is_miss_not_tampering(self) -> None:
        """A signed, hash-verified blob whose deserializer fails (e.g. a CUDA
        tensor on a CPU-only host) is authentic — not tampering. It must
        recompute (miss) in every mode, including strict, rather than raise a
        spurious CacheSignatureError blaming corruption."""
        from unittest import mock

        signer, verifier = _keypair()
        writer = self._loader(signer=signer)
        writer.save_cache(
            _simple_cache(hash_val="deser_fail", pt=_Point(1, 2))
        )
        writer.flush()

        def _boom(_data: bytes, _type_hint: str | None = None) -> Any:
            raise RuntimeError("deserializer cannot run in this environment")

        reader = self._loader(signer=verifier, mode="strict")
        with mock.patch.dict(
            "marimo._save.loaders.lazy.BLOB_DESERIALIZERS",
            {".pickle": _boom},
        ):
            # Hash verifies (bytes untouched); only deserialization fails →
            # miss, not CacheSignatureError.
            assert reader.load_cache(key("deser_fail")) is None


# ---------------------------------------------------------------------------
# fingerprint primitive
# ---------------------------------------------------------------------------


class TestFingerprint:
    def test_fingerprint_format_and_stability(self) -> None:
        _, pub = generate_keypair()
        fp = fingerprint(pub)
        assert fp.startswith("SHA256:")
        assert "=" not in fp  # unpadded
        assert fingerprint(pub) == fp  # deterministic

    def test_fingerprint_matches_signer_method(self) -> None:
        _, pub = generate_keypair()
        signer = CacheSigner.from_public_key_pem(pub)
        assert signer.fingerprint() == fingerprint(pub)

    def test_distinct_keys_distinct_fingerprints(self) -> None:
        _, pub_a = generate_keypair()
        _, pub_b = generate_keypair()
        assert fingerprint(pub_a) != fingerprint(pub_b)


# ---------------------------------------------------------------------------
# WASM: signature failures evict the fetched bytes
# ---------------------------------------------------------------------------


class TestWasmSignatureEviction:
    """A signed-blob mismatch in WASM must evict the HTTP-fetched bytes from
    the session store (and poison the keys) so tampered data is neither
    re-served nor swept into an export bundle via export_keys()."""

    @pytest.fixture(autouse=True)
    def _isolate_poisoned_keys(self) -> Any:
        from marimo._save.loaders.lazy import _cache_state

        poisoned = _cache_state().poisoned_keys
        snapshot = set(poisoned)
        yield
        poisoned.clear()
        poisoned.update(snapshot)

    def test_tampered_blob_evicted_and_poisoned_in_verify(self) -> None:
        from unittest import mock

        from marimo._save.loaders.lazy import (
            WasmLazyLoader,
            WasmLazyStore,
            _cache_state,
        )
        from marimo._save.stores.dict_store import DictStore

        signer, verifier = _keypair()
        store = WasmLazyStore(inner=DictStore())
        writer = WasmLazyLoader("wasm_sig", store=store, signer=signer)
        writer.save_cache(
            _simple_cache(hash_val="wasm_tamper", secret={"k": "v"})
        )
        writer.flush()

        # Overwrite the pickle blob in the session store with different bytes.
        blob_key = next(
            k for k in store.export_keys() if k.endswith(".pickle")
        )
        store._inner.put(blob_key, pickle.dumps({"injected": True}))

        reader = WasmLazyLoader("wasm_sig", store=store, signer=verifier)
        # No network: the tampered blob is already resident in the inner store,
        # and evicted keys must not trigger a real fetch.
        with mock.patch.object(
            store, "_http_get_batch", return_value=iter([])
        ):
            assert reader.load_cache(key("wasm_tamper")) is None

        manifest_path = str(reader.build_path(key("wasm_tamper")))
        assert blob_key in _cache_state().poisoned_keys
        assert manifest_path in _cache_state().poisoned_keys
        assert not store.hit(blob_key)
        # The rejected blob is no longer advertised for export bundling.
        assert blob_key not in store.export_keys()
