# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import hashlib
import importlib
import inspect
import math
import pickle
import queue
import threading
from enum import Enum, auto
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import msgspec

from marimo import _loggers
from marimo._runtime.context import safe_get_context
from marimo._runtime.primitives import (
    is_data_primitive,
    is_data_primitive_container,
    is_primitive,
)
from marimo._save.cache import (
    MARIMO_CACHE_VERSION,
    Cache,
    CacheState,
)
from marimo._save.encode import common_container_to_bytes, data_to_buffer
from marimo._save.hash import DEFAULT_HASH, HashKey
from marimo._save.loaders.loader import BasePersistenceLoader
from marimo._save.signing import (
    CacheSignatureError,
    CacheSigner,
    _get_default_signer,
    _sha256hex,
    fingerprint,
)
from marimo._save.stores import DEFAULT_STORE, FileStore, Store

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
from marimo._save.stubs import (
    ClassStub,
    FunctionStub,
    ModuleStub,
)
from marimo._save.stubs.lazy_stub import (
    BLOB_DESERIALIZERS,
    BLOB_SERIALIZERS,
    LAZY_STUB_LOOKUP,
    Cache as CacheSchema,
    CacheType,
    ImmediateReferenceStub,
    Item,
    Meta,
    ReferenceStub,
    UnhashableStub,
)
from marimo._save.stubs.stubs import mro_lookup

LOGGER = _loggers.marimo_logger()


class _Unset:
    """Sentinel for LazyLoader.signer default — distinguishes 'not provided'
    from explicit `None` (which opts out of signing entirely)."""


_SIGNER_UNSET = _Unset()

# Verification posture. `off`: no signing or verification (legacy / opt-out).
# `verify` (default): sign on write, and on read serve only entries that
# verify against a trusted key — unverifiable entries miss and recompute
# (fail-safe). `strict`: like verify, but an unverifiable entry raises
# (fail-closed).
_VALID_MODES = ("off", "verify", "strict")


# Fingerprint digests use standard base64 (matching `ssh-keygen -lf`
# presentation). Accept a urlsafe-encoded paste too and canonicalize it so it
# still matches fingerprint() output.
_FP_URLSAFE_TO_STD = str.maketrans("-_", "+/")


def _normalize_fingerprint(fp: str) -> str:
    """Validate and canonicalize one `"SHA256:<base64>"` fingerprint.

    Accepts standard or urlsafe base64, padded or unpadded, and returns the
    canonical form produced by :func:`marimo._save.signing.fingerprint`
    (standard base64, no padding). Raising on a malformed digest here turns a
    fat-fingered fingerprint into a configuration-time error rather than a
    permanent, silent cache miss (the digest would validate on prefix alone but
    never match a real key).
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
            f"Invalid trusted_signers fingerprint {fp!r}; the digest is not "
            "valid base64."
        ) from e
    if len(raw) != 32:
        raise ValueError(
            f"Invalid trusted_signers fingerprint {fp!r}; expected a SHA-256 "
            f"(32-byte) digest, got {len(raw)} byte(s)."
        )
    # Re-encode from the decoded bytes rather than returning `body` verbatim.
    # base64 of 32 bytes has 2 unused ("slack") bits in the final character, so
    # several distinct final characters decode to the same digest; returning
    # the raw text would let such a variant validate here yet never match the
    # canonical form emitted by signing.fingerprint() — a permanent silent miss.
    return "SHA256:" + base64.b64encode(raw).decode("ascii").rstrip("=")


def _normalize_fingerprints(value: Iterable[str] | None) -> set[str]:
    """Validate and collect `trusted_signers` fingerprint strings.

    Rejects a bare `str` (which would otherwise iterate into single
    characters — a silent-miss footgun) and canonicalizes each entry via
    :func:`_normalize_fingerprint` so a padded or urlsafe paste still matches
    :func:`marimo._save.signing.fingerprint` output.
    """
    if value is None:
        return set()
    if isinstance(value, str):
        raise TypeError(
            "trusted_signers must be an iterable of fingerprint strings, not "
            "a single str. Wrap it in a set/list: trusted_signers={fp}."
        )
    return {_normalize_fingerprint(fp) for fp in value}


class _BlobStatus(Enum):
    """Sentinel placed in the results queue for a blob that yielded no value.

    `MISSING`: the store had no bytes for the key — under a verified manifest a
    genuine gap is an integrity anomaly. `UNREADABLE`: bytes were present and
    hash-verified but the deserializer failed (an environment issue, e.g. a
    CUDA tensor on a CPU-only host) — authentic, so recompute rather than flag
    tampering.
    """

    MISSING = auto()
    UNREADABLE = auto()


# Domain-separation tag prepended to manifest signable bytes, binding a
# signature to this purpose and format version independent of payload shape.
_MANIFEST_SIG_CONTEXT = b"marimo-cache-manifest:v1:"


def _signable_bytes(schema: CacheSchema) -> bytes:
    """Return the canonical bytes to sign or verify for a cache manifest.

    Clears the `signature` envelope field so save and restore operate on
    identical input. The manifest structs set `omit_defaults` (see
    `lazy_stub.py`), so these bytes stay stable across additive,
    absent-defaulted schema changes; any other schema change must bump
    `MARIMO_CACHE_VERSION`.
    """
    unsigned_meta = msgspec.structs.replace(schema.meta, signature=None)
    return _MANIFEST_SIG_CONTEXT + msgspec.json.encode(
        msgspec.structs.replace(schema, meta=unsigned_meta)
    )


def _is_local_file_store(store: Store) -> bool:
    """True when a loader's blobs live on the local filesystem, so a
    machine-local auto-generated signing key is meaningful (single-machine
    trust).

    `LazyStore` wraps its backend by composition rather than subclassing
    `FileStore`, so unwrap to the inner store. Shared/remote backends
    (Redis, REST) and the WASM HTTP store (`DictStore` inner) return
    `False` — their entries can't be verified by a key only this machine
    holds.
    """
    if isinstance(store, LazyStore):
        return isinstance(store._inner, FileStore)
    return isinstance(store, FileStore)


def _is_trusted_origin_store(store: Store) -> bool:
    """True when a verify capability gap may degrade to `off` (serve
    unverified) instead of missing every read."""
    # NB. WASM blobs are fetched same-origin from the notebook location; an
    # attacker who can swap them already controls the notebook code served
    # from that origin, so verification adds nothing. Shared/remote stores are
    # what signing protects, so they are never trusted (no degrade).
    if isinstance(store, WasmLazyStore):
        return True
    return _is_local_file_store(store)


def _verify_signed_blob(
    key: str,
    data: bytes,
    blob_hash_map: dict[str, str] | None,
    effective_signer: CacheSigner | None,
) -> None:
    """Check a fetched blob against its signed hash before deserialization.

    No-op for unsigned entries (`effective_signer is None`). For a verified
    manifest, a *missing* hash is itself a signature error: the signed manifest
    and the blob set must agree, so a hash-less reference means writer drift or
    tampering rather than a reason to skip the check (which would otherwise let
    a blob reach `pickle.loads` unverified — even in strict mode).
    """
    if effective_signer is None:
        return
    expected_hash = (blob_hash_map or {}).get(key)
    if expected_hash is None:
        raise CacheSignatureError(
            f"A signed cache entry is missing the integrity hash for blob "
            f"{key!r}. The cached data may be corrupted or was modified "
            f"outside of marimo.\n"
            f"To recover, call cache_clear() on the cached function or "
            f"context manager."
        )
    effective_signer.verify_blob(key, data, expected_hash)


def _incomplete_cache_error(
    effective_signer: CacheSigner | None,
) -> Exception:
    """Error for a cache entry missing one or more blobs."""
    # NB. under a verified manifest the blob set is authenticated, so a missing
    # blob is a trust anomaly: raise CacheSignatureError so strict fails closed
    # (verify still misses). Unsigned entries stay a plain miss.
    if effective_signer is not None:
        return CacheSignatureError(
            "A signed cache entry is missing one or more blobs. The cached "
            "data may be corrupted or was modified outside of marimo.\n"
            "To recover, call cache_clear() on the cached function or "
            "context manager."
        )
    return FileNotFoundError("Incomplete cache: missing blobs")


def _module_available(type_hint: str | None) -> bool:
    """True if the root module of `type_hint` can be imported here.

    Lets the caller skip fetching a blob whose deserializer needs an absent
    module (e.g. `torch` in a torch-free browser). Empty hint or `__main__` is
    treated as available (resolved elsewhere), so we never skip a fetch we
    can't reason about.
    """
    if not type_hint:
        return True
    root = type_hint.split(".", 1)[0]
    if root == "__main__":
        return True
    import importlib.util

    try:
        return importlib.util.find_spec(root) is not None
    except (ImportError, ValueError):
        return False


def maybe_update_lazy_stub(value: Any) -> str:
    value_type = type(value)
    # MRO not that expensive, type hashable for functools lookup.
    result = mro_lookup(value_type, LAZY_STUB_LOOKUP)
    loader = result[1] if result else "pickle"
    return loader


def _maybe_content_digest(value: Any, hash_type: str = DEFAULT_HASH) -> str:
    """Hex content digest for an array-like data primitive, else `""`.

    Mirrors the hasher's content serialization (`data_to_buffer` /
    `common_container_to_bytes`). Plain primitives are excluded: they restore
    inline, so a consumer content-hashes the real value directly.
    """
    if is_primitive(value):
        return ""
    if is_data_primitive(value):
        serial = data_to_buffer(value)
    elif is_data_primitive_container(value):
        serial = common_container_to_bytes(value)
    else:
        return ""
    return hashlib.new(hash_type, serial, usedforsecurity=False).digest().hex()


def _maybe_import_ref(value: Any) -> tuple[str, str] | None:
    """Return `(module, qualname)` if *value* is re-importable by name,
    else `None`.
    """
    if not (
        inspect.isclass(value)
        or inspect.isroutine(value)
        or type(value).__module__ == "typing"
    ):
        return None
    module = getattr(value, "__module__", None)
    qualname = (
        getattr(value, "__qualname__", None)
        or getattr(value, "__name__", None)
        or getattr(value, "_name", None)
    )
    if not module or module == "__main__" or not qualname:
        return None
    try:
        obj: Any = importlib.import_module(module)
        for part in qualname.split("."):
            obj = getattr(obj, part)
    except (ImportError, AttributeError):
        return None
    return (module, qualname) if obj is value else None


# Token <-> value for non-finite floats, inlined in Item.special_float rather
# than pickled (see the field for why they can't use Item.primitive).
_NON_FINITE_FLOATS: dict[str, float] = {
    "nan": float("nan"),
    "inf": float("inf"),
    "-inf": float("-inf"),
}


def _non_finite_token(value: float) -> str:
    if math.isnan(value):
        return "nan"
    return "inf" if value > 0 else "-inf"


def to_item(
    path: Path,
    value: Any | None,
    var_name: str = "",
    loader: str | None = None,
    hash: str | None = "",  # noqa: A002
) -> Item:
    if value is None:
        return Item()

    if loader is None:
        loader = maybe_update_lazy_stub(value)

    type_hint = f"{type(value).__module__}.{type(value).__name__}"

    if loader == "pickle":
        # A re-importable reference is stored inline rather than as a blob.
        ref = _maybe_import_ref(value)
        if ref is not None:
            return Item(import_ref=ref)
    if loader in ("pickle", "npy", "arrow", "pt"):
        # Blob strategies: the file extension is the loader name, matching
        # the path `save_cache` writes (`{var}.{loader}`). Listing them
        # together keeps a new format (e.g. `pt`) from silently falling
        # through to the `.pickle` fallback and mismatching its blob.
        return Item(
            reference=(path / f"{var_name}.{loader}").as_posix(),
            hash=hash,
            type_hint=type_hint,
        )
    if loader == "ui":
        return Item(reference=(path / "ui.pickle").as_posix())
    if isinstance(value, FunctionStub):
        return Item(function=value.dump())
    if isinstance(value, ClassStub):
        return Item(class_def=value.dump())
    if isinstance(value, ModuleStub):
        return Item(
            module=value.name,
            module_version=value.version or None,
        )
    # bool must be tested before int (bool is a subclass of int).
    # Coerce scalar subclasses (e.g. numpy.float64, numpy.int32) to plain
    # Python types so msgspec.json.encode can serialise them.
    if isinstance(value, bool):
        return Item(primitive=bool(value))
    if isinstance(value, int):
        return Item(primitive=int(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            return Item(special_float=_non_finite_token(value))
        return Item(primitive=float(value))
    # NB. no `bytes`: msgspec JSON-encodes it to a base64 str that restores as
    # str, corrupting the value (bytes route to "pickle" via LAZY_STUB_LOOKUP).
    if isinstance(value, (str, type(None))):
        return Item(primitive=value)

    return Item(
        reference=(path / f"{var_name}.pickle").as_posix(),
        hash=hash,
        type_hint=type_hint,
    )


def from_item(item: Item, var_name: str = "") -> Any:
    if item.unserializable_type is not None:
        # No blob written — rebuild the `UnhashableStub` from the marker. NB.
        # carry any persisted digest so a consumer reproduces its key from it.
        return UnhashableStub(
            var_name=var_name,
            type_name=item.unserializable_type,
            content_hash=item.hash or "",
        )
    if item.reference is not None:
        return ImmediateReferenceStub(
            ReferenceStub(item.reference, hash_value=item.hash or "")
        )
    if item.module is not None:
        mod_stub = ModuleStub.__new__(ModuleStub)
        mod_stub.name = item.module
        mod_stub.version = item.module_version or ""
        return mod_stub
    if item.import_ref is not None:
        module, qualname = item.import_ref
        obj: Any = importlib.import_module(module)
        for part in qualname.split("."):
            obj = getattr(obj, part)
        return obj
    if item.function is not None:
        return FunctionStub.from_dump(item.function)
    if item.class_def is not None:
        return ClassStub.from_dump(item.class_def)
    if item.special_float is not None:
        # A corrupted/unknown token can only arise in a tampered manifest,
        # which verify/strict reject before reaching here; fall back to nan.
        return _NON_FINITE_FLOATS.get(item.special_float, float("nan"))
    if item.primitive is not None:
        return item.primitive
    return None


# Fallback to a process-local CacheState.
_FALLBACK_CACHE_STATE: CacheState | None = None


def _cache_state() -> CacheState:
    """Cache state for the current session, scoped to the root context."""
    ctx = safe_get_context()
    if ctx is not None:
        while ctx.parent is not None:
            ctx = ctx.parent
        return ctx.cache
    global _FALLBACK_CACHE_STATE
    if _FALLBACK_CACHE_STATE is None:
        _FALLBACK_CACHE_STATE = CacheState(store=DEFAULT_STORE())
    return _FALLBACK_CACHE_STATE


def _get_wasm_dict_store() -> Store:
    """The session's shared in-memory WASM store, created on first use."""
    cache_state = _cache_state()
    if cache_state.wasm_dict_store is None:
        from marimo._save.stores.dict_store import DictStore

        cache_state.wasm_dict_store = DictStore()
    return cache_state.wasm_dict_store


def flush_active_caches() -> None:
    """Drain pending writes for every active loader (durability on exit)."""
    LazyLoader.flush_all()


def dump_cache_manifests(manifest_name: str) -> None:
    """Write this session's produced keys into each file-backed cache dir.

    An out-of-process exporter (`html-wasm --execute`) reads `manifest_name` to
    discover what to bundle. In-memory stores (the WASM `DictStore`) are skipped
    — nothing on disk. The loop only matters for multi-cache-block notebooks.
    """
    loaders = LazyLoader.active_loaders()
    keys = LazyLoader.export_keys()
    seen: set[Path] = set()
    for loader in loaders:
        store = loader.store
        inner = store._inner if isinstance(store, LazyStore) else None
        if not isinstance(inner, FileStore):
            continue
        cache_dir = inner.save_path
        if cache_dir in seen:
            continue
        seen.add(cache_dir)
        _write_export_manifest(cache_dir, manifest_name, keys)


def _write_export_manifest(
    cache_dir: Path, manifest_name: str, keys: list[str]
) -> None:
    """Atomically (re)write the export manifest in `cache_dir`."""
    import json
    import os

    # NB. temp file + os.replace so a reader never sees a half-written
    # manifest, and a mid-write kill leaves the previous one intact.

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache_dir / f"{manifest_name}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(keys))
        os.replace(tmp, cache_dir / manifest_name)
    except OSError as e:
        LOGGER.warning("Failed to write cache export manifest: %s", e)


class LazyStore(Store):
    """Native store for `LazyLoader`.

    Delegates to an inner store (default `FileStore` at `__marimo__/cache/`)
    and tracks which keys were written or read."""

    def __init__(self, inner: Store | None = None) -> None:
        self._inner = inner if inner is not None else FileStore()
        self._written_keys: set[str] = set()
        # Keys read this session. A warm re-export hits the cache rather
        # than re-writing it, so the export manifest must cover reads too
        # or the bundle ships incomplete.
        self._touched_keys: set[str] = set()

    def get(self, key: str) -> bytes | None:
        result = self._inner.get(key)
        if result is not None:
            self._touched_keys.add(key)
        return result

    def put(self, key: str, value: bytes) -> bool:
        self._written_keys.add(key)
        return self._inner.put(key, value)

    def hit(self, key: str) -> bool:
        result = self._inner.hit(key)
        if result:
            self._touched_keys.add(key)
        return result

    def clear(self, key: str) -> bool:
        self._written_keys.discard(key)
        self._touched_keys.discard(key)
        return self._inner.clear(key)

    def export_keys(self) -> list[str]:
        return sorted(self._written_keys | self._touched_keys)


class WasmLazyStore(LazyStore):
    """WASM store: writes to a shared in-session `DictStore`; reads fall
    through to HTTP fetch from `notebook_location()/public/cache/`.
    """

    def __init__(self, inner: Store | None = None) -> None:
        super().__init__(
            inner if inner is not None else _get_wasm_dict_store()
        )

    def get(self, key: str) -> bytes | None:
        result = super().get(key)
        if result is not None:
            return result
        if key not in _cache_state().poisoned_keys:
            return self._http_get(key)
        return None

    def get_batch(
        self, keys: Iterable[str]
    ) -> Iterator[tuple[str, bytes | None]]:
        # Inner store first; HTTP-fetch only the (unpoisoned) misses, fired
        # concurrently.
        poisoned = _cache_state().poisoned_keys
        http_keys: list[str] = []
        for k in keys:
            data = self._inner.get(k)
            if data is not None:
                self._touched_keys.add(k)
                yield k, data
            elif k not in poisoned:
                http_keys.append(k)
            else:
                yield k, None
        if http_keys:
            yield from self._http_get_batch(http_keys)

    def _base_url(self) -> str:
        from marimo._runtime.runtime import notebook_location

        loc = notebook_location()
        return f"{loc}/public/cache" if loc else "public/cache"

    @staticmethod
    def _sanitize_key(key: str) -> str:
        """Validate a fetch key against path traversal."""
        clean = PurePosixPath(key)
        if ".." in clean.parts or clean.is_absolute():
            raise ValueError(f"Invalid cache key: {key}")
        return key

    def _http_get(self, key: str) -> bytes | None:
        """Single sync fetch via pyodide_http-patched urllib."""
        import urllib.request

        url = f"{self._base_url()}/{self._sanitize_key(key)}"
        try:
            with urllib.request.urlopen(url) as resp:
                data = resp.read() if resp.status == 200 else None
        except Exception:
            return None
        if data is not None:
            self._inner.put(key, data)
            self._touched_keys.add(key)
        return data

    def _http_get_batch(
        self, keys: Iterable[str]
    ) -> Iterator[tuple[str, bytes | None]]:
        """Fire all fetches concurrently via JS fetch + asyncio.gather."""
        import asyncio

        from js import fetch  # type: ignore

        base = self._base_url()
        keys_list = [self._sanitize_key(k) for k in keys]
        loop = asyncio.get_event_loop()

        async def _fetch_one(key: str) -> tuple[str, bytes | None]:
            resp = await fetch(f"{base}/{key}")
            if resp.ok:
                buf = await resp.arrayBuffer()
                return key, buf.to_bytes()
            return key, None

        async def _fetch_all() -> list[tuple[str, bytes | None]]:
            return await asyncio.gather(*(_fetch_one(k) for k in keys_list))

        try:
            results = loop.run_until_complete(_fetch_all())
        except Exception:
            # run_until_complete on the live pyodide loop requires JSPI
            # (WebAssembly stack switching), which e.g. Firefox lacks. Fall
            # back to sequential synchronous XHR via the pyodide_http-patched
            # urllib — legal in a worker.
            results = [(k, self._http_get(k)) for k in keys_list]
        # Cache successful fetches in-session (idempotent for the fallback
        # path, which already wrote via `_http_get`) so repeat reads stay
        # local and the export manifest covers HTTP-fetched blobs.
        for key, data in results:
            if data is not None:
                self._inner.put(key, data)
                self._touched_keys.add(key)
            yield key, data


class LazyLoader(BasePersistenceLoader):
    _store_cls: type[Store] = LazyStore

    def __init__(
        self,
        name: str,
        store: Store | None = None,
        signer: CacheSigner | None | _Unset = _SIGNER_UNSET,
        trusted_signers: Iterable[str] | None = None,
        mode: str = "verify",
    ) -> None:
        """Create a LazyLoader.

        Args:
            name: Cache namespace / directory name.
            store: Backing store.  Defaults to `LazyStore` (file-based).
            signer: :class:`~marimo._save.signing.CacheSigner` for Ed25519
                manifest signing (write) and verification (read).  A loader
                always trusts its own signer's key, so the common case — one
                signer that both signs and verifies — needs nothing else.
                Pass `signer=None` to explicitly disable signing.  When
                omitted, a signer is resolved automatically: env vars
                `MARIMO_CACHE_SIGNING_PRIVATE_KEY` /
                `MARIMO_CACHE_SIGNING_PUBLIC_KEY` take precedence, then a
                saved key in `marimo_state_dir()/cache_signing_key.pem`; if
                neither exists a fresh key is generated and saved there (local
                file stores only — shared/remote stores use only an explicitly
                configured key, since an auto key is unverifiable elsewhere).
                Resolves to `None` (unsigned) when the `cryptography`
                package is not installed.
            trusted_signers: Fingerprint strings (`"SHA256:<base64>"` from
                :func:`~marimo._save.signing.fingerprint`) that this loader
                trusts, in addition to its own signer (always trusted for its
                own writes).  An entry verifies when it is signed directly by a
                trusted fingerprint's key.  Padded or urlsafe fingerprints are
                normalized to canonical form.
            mode: Verification posture — `"off"`, `"verify"` (default), or
                `"strict"`.  `off` neither signs nor verifies (legacy
                opt-out).  `verify` signs on write and, on read, serves only
                entries that verify against a trusted key; an unverifiable
                entry misses and is recomputed (fail-safe).  `strict` is like
                `verify` but raises
                :class:`~marimo._save.signing.CacheSignatureError` on an
                unverifiable entry (fail-closed).  `strict` also requires a
                signing/verification capability at construction; `verify`
                degrades to `off` (with a one-time warning) when none exists.
        """
        if (
            not isinstance(signer, (_Unset, CacheSigner))
            and signer is not None
        ):
            raise TypeError(
                "signer must be a CacheSigner or None, got "
                f"{type(signer).__name__}."
            )
        if mode not in _VALID_MODES:
            raise ValueError(
                f"Invalid cache signing mode {mode!r}; expected one of "
                f"{', '.join(_VALID_MODES)}."
            )
        loaders = _cache_state().active_lazy_loaders
        if store is None:
            # Reuse the store across recreations of a named loader (State GC,
            # partial reconstruction) so cached data survives.
            prev = loaders.get(name)
            store = prev.store if prev is not None else self._store_cls()
        super().__init__(name, "jsonl", store)
        self._pending: list[threading.Thread] = []
        self._trusted_fingerprints = _normalize_fingerprints(trusted_signers)
        self._mode = mode
        self._degrade_warned = False
        self._write_skip_warned = False
        # Store the signer unresolved (the `signer` property auto-resolves an
        # `_Unset` sentinel on first access). Deferring means mode='off' — which
        # never signs or verifies — doesn't load or mint a machine-local key
        # (avoiding a stray cache_signing_key.pem and read-only-state-dir
        # warnings for a caller who opted out). verify/strict resolve it below.
        self._signer: CacheSigner | _Unset | None = signer
        # Fail fast on an impossible strict configuration (no crypto, or no
        # signer and no trusted_signers). This reads `self.signer` for
        # verify/strict (resolving the key), but returns early for 'off'.
        # Register only afterwards so a rejected loader never lingers in the
        # active registry (which would otherwise be returned to a later
        # same-named lookup).
        self._effective_mode()
        loaders[name] = self

    def _resolve_unset_signer(self) -> CacheSigner | None:
        """Auto-resolve the signer for an unset value, matching __init__.

        A local file store auto-generates (or loads) a machine-local key so the
        loader signs its own writes — *even when* `trusted_signers` is also
        configured. Composing trust with signing this way means adding a
        teammate's fingerprint to also trust their caches never silently turns
        off signing of our own writes (which would otherwise leave the loader
        read-only). Shared/remote stores don't auto-generate — an auto key is
        unverifiable by other machines — so they use only an explicitly
        configured (env/config) key.
        """
        return _get_default_signer(
            auto_generate=_is_local_file_store(self.store)
        )

    def _effective_mode(self) -> str:
        """Resolve the verification mode after capability checks.

        `verify` degrades to `off` (with a one-time warning) when there is
        nothing to verify with — no `cryptography` package, or neither a
        signer nor `trusted_signers`. `strict` instead raises, so a
        fail-closed loader never silently serves unverified data. Recomputed
        on each load/save (not cached) so a reconfigure via `setattr` — which
        applies kwargs in caller order — is always honored.
        """
        if self._mode == "off":
            return "off"

        from marimo._dependencies.dependencies import DependencyManager

        if not DependencyManager.cryptography.has():
            if self._mode == "strict":
                raise ValueError(
                    "mode='strict' cache signing requires the 'cryptography' "
                    "package, which is not installed."
                )
            reason = "the 'cryptography' package is not installed"
            # NB. A trusted-origin store degrades to 'off'; a shared/remote
            # store keeps 'verify' (so every read misses and writes are skipped)
            # rather than serving the unverified bytes signing protects.
            if _is_trusted_origin_store(self.store):
                self._warn_degraded(reason)
                return "off"
            self._warn_no_trust_anchor(reason)
            return "verify"
        if self.signer is None and not self._trusted_fingerprints:
            if self._mode == "strict":
                raise ValueError(
                    "mode='strict' requires a signer or trusted_signers to "
                    "verify against, but neither is configured. Pass "
                    "signer=CacheSigner.from_public_key_pem(...) or "
                    "trusted_signers={fingerprint, ...}."
                )
            # Same trusted-origin split as the no-cryptography branch.
            if _is_trusted_origin_store(self.store):
                self._warn_degraded(
                    "no signer or trusted_signers is configured"
                )
                return "off"
            self._warn_no_trust_anchor("no signer or trusted_signers is set")
            return "verify"
        return self._mode

    def _warn_degraded(self, reason: str) -> None:
        if not self._degrade_warned:
            self._degrade_warned = True
            LOGGER.warning(
                "LazyLoader mode=%r degraded to 'off' because %s; cache "
                "entries are neither signed nor verified.",
                self._mode,
                reason,
            )

    def _warn_no_trust_anchor(self, reason: str) -> None:
        """One-time warning: a shared/remote store has no way to verify.

        Unlike the local degrade-to-off path, 'verify' is kept so unverified
        bytes are never served — the consequence is that every read misses and
        every write is skipped until the loader can verify again (`reason`
        names what's missing).
        """
        if not self._degrade_warned:
            self._degrade_warned = True
            LOGGER.warning(
                "LazyLoader mode=%r cannot verify cache entries for a "
                "shared/remote store (%s): every read misses and writes are "
                "skipped. Install 'cryptography' and set "
                "MARIMO_CACHE_SIGNING_PRIVATE_KEY (to sign+verify) or "
                "MARIMO_CACHE_SIGNING_PUBLIC_KEY (to verify only), or pass "
                "trusted_signers=..., to use the cache; or mode='off' to cache "
                "without signing.",
                self._mode,
                reason,
            )

    # Property accessors so LoaderPartial.create_or_reconfigure() can update
    # signer / trusted_signers / mode via setattr() using the constructor
    # argument names.
    @property
    def signer(self) -> CacheSigner | None:
        # Auto-resolve the _Unset sentinel on first access. In 'off' mode we
        # never sign or verify, so don't load or mint a key — return None
        # without caching it, so a later reconfigure to verify/strict still
        # resolves (see __init__).
        if isinstance(self._signer, _Unset):
            if self._mode == "off":
                return None
            self._signer = self._resolve_unset_signer()
        return self._signer

    @signer.setter
    def signer(self, value: CacheSigner | None | _Unset) -> None:
        # Validate up front (mirrors __init__) so a bad reconfigure fails here
        # rather than as an AttributeError mid-save.
        if not isinstance(value, (_Unset, CacheSigner)) and value is not None:
            raise TypeError(
                "signer must be a CacheSigner or None, got "
                f"{type(value).__name__}."
            )
        # NB. store the sentinel unresolved; the `signer` property defers
        # resolution (and skips it in 'off' mode). Resolving here would
        # mint/load a machine-local key when reconfiguring an off-mode loader.
        self._signer = value

    @property
    def trusted_signers(self) -> frozenset[str]:
        # Frozen copy so mutating the return value can't bypass
        # _normalize_fingerprints — assign to the property to change trust.
        return frozenset(self._trusted_fingerprints)

    @trusted_signers.setter
    def trusted_signers(self, value: Iterable[str] | None) -> None:
        self._trusted_fingerprints = _normalize_fingerprints(value)

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        # No capability fail-fast here: create_or_reconfigure() applies kwargs
        # via setattr in caller order, so a signer set in the same reconfigure
        # may not be applied yet. _effective_mode() enforces the capability
        # invariant at load/save time; __init__ enforces it for direct
        # construction.
        if value not in _VALID_MODES:
            raise ValueError(
                f"Invalid cache signing mode {value!r}; expected one of "
                f"{', '.join(_VALID_MODES)}."
            )
        self._mode = value

    def flush(self) -> None:
        """Wait for all pending background writes to complete."""
        for t in self._pending:
            t.join()
        self._pending.clear()

    @classmethod
    def flush_all(cls) -> None:
        """Drain pending background writes for every active loader."""
        for loader in cls.active_loaders():
            loader.flush()

    @classmethod
    def export_keys(cls) -> list[str]:
        """Keys this session produced, merged across every active loader.

        Flush first if the result must reflect pending background writes.
        """
        return sorted(
            {
                key
                for loader in cls.active_loaders()
                for key in loader.store.export_keys()
            }
        )

    @classmethod
    def active_loaders(cls) -> list[LazyLoader]:
        """Loaders the current session has created (for flush/export)."""
        return list(_cache_state().active_lazy_loaders.values())

    def mark_stale(self, manifest_key: str) -> None:
        """Force this manifest to miss for the rest of the session."""
        _cache_state().stale_keys.add(manifest_key)

    def load_cache(
        self,
        key: HashKey,
        glbls: dict[str, Any] | None = None,
    ) -> Cache | None:
        del glbls
        # Resolve the effective mode before the try so an impossible strict
        # configuration surfaces as a ValueError rather than being swallowed
        # as a generic miss by the except clause below.
        mode = self._effective_mode()
        manifest_key = str(self.build_path(key))
        # Invalidated for re-execution this session.
        if manifest_key in _cache_state().stale_keys:
            return None
        blob: bytes | None = None
        try:
            blob = self.store.get(manifest_key)
            if not blob:
                return None
            return self.restore_cache(key, blob)
        except CacheSignatureError as e:
            # Evict the rejected manifest + its blobs. On WASM this clears the
            # HTTP-fetched bytes from the session store (and poisons the keys
            # so they aren't re-fetched), so tampered data can't be re-served
            # or swept into a later export bundle via export_keys(); no-op
            # natively, where a non-strict recompute overwrites the entry.
            # Any manifest that fails to verify against a trusted key reaches
            # here (bad signature, unsigned, or an untrusted key), so it is
            # never served unverified — see _resolve_effective_signer.
            self._on_restore_failure(key, blob)
            if mode == "strict":
                raise
            # verify (fail-safe): degrade to cache miss rather than crashing;
            # the entry is recomputed rather than served unverified.
            LOGGER.warning(
                "Cache signature verification failed (treating as "
                "cache miss): %s",
                e,
            )
            return None
        except Exception as e:
            LOGGER.warning("Failed to restore lazy cache: %s", e)
            self._on_restore_failure(key, blob)
            return None

    def _on_restore_failure(
        self, key: HashKey, manifest_blob: bytes | None
    ) -> None:
        """Hook after a failed restore. No-op natively; the WASM variant
        evicts and poisons the bad keys so HTTP won't re-fetch them."""

    def _direct_candidates(self, cache_data: CacheSchema) -> list[CacheSigner]:
        """Candidate verifier keys for the direct path, in priority order:
        this loader's own signer (always trusted for its own writes), then the
        manifest's declared signer key when its fingerprint is in
        `trusted_signers`."""
        candidates: list[CacheSigner] = []
        own = self.signer
        if own is not None:
            candidates.append(own)
        declared = cache_data.meta.signer_public_key
        if declared:
            try:
                if fingerprint(declared) in self._trusted_fingerprints:
                    candidates.append(
                        CacheSigner.from_public_key_pem(declared)
                    )
            except Exception:
                # A malformed/unsupported declared key can't be a direct
                # candidate (parsing it can raise ValueError,
                # CacheSignatureError, or cryptography's UnsupportedAlgorithm,
                # none of which subclass a common base) — swallow it here so a
                # strict loader still raises "unverifiable" downstream instead
                # of escaping to the generic-miss handler. The own-signer
                # candidate may still verify.
                pass
        return candidates

    def _resolve_effective_signer(
        self, cache_data: CacheSchema, mode: str
    ) -> CacheSigner | None:
        """Verify the manifest and return the signer that validated it.

        In `off` mode returns `None` without checking (data served as-is).
        In `verify`/`strict` the entry must verify against a trusted key:
        this loader's own signer (implicitly trusted for its own writes), or
        the manifest's declared signer key when its fingerprint is in
        `trusted_signers`. Anything else raises `CacheSignatureError`, so
        unverifiable data is recomputed (verify) or rejected (strict) — never
        deserialized.

        Returning the verifying signer (non-`None`) enables the blob-hash
        checks downstream.

        Note: a cache written by another machine's auto-generated key on a
        shared or committed cache dir won't match any trusted fingerprint, so
        it misses (recomputes) rather than being accepted. To share a cache
        across machines, configure a shared signing key
        (`MARIMO_CACHE_SIGNING_*`) or add the writer's fingerprint to
        `trusted_signers`.
        """
        if mode == "off":
            return None

        sig = cache_data.meta.signature
        if sig is None:
            raise CacheSignatureError(
                f"A cache entry is unsigned, but this loader verifies cache "
                f"signatures (mode={self._mode!r}). The entry may predate "
                f"signing or was tampered with; it will be recomputed.\n"
                f"To recover, call cache_clear() on the cached function or "
                f"context manager."
            )

        signable = _signable_bytes(cache_data)
        for verifier in self._direct_candidates(cache_data):
            try:
                verifier.verify(signable, sig)
                return verifier
            except CacheSignatureError:
                continue

        raise CacheSignatureError(
            "A cache entry could not be verified against any trusted signer — "
            "its signature is invalid or was made by an untrusted key. The "
            "entry will be recomputed.\n"
            "To recover, call cache_clear() on the cached function or context "
            "manager."
        )

    def restore_cache(self, key: HashKey, blob: bytes) -> Cache:
        mode = self._effective_mode()
        try:
            cache_data = msgspec.json.decode(blob, type=CacheSchema)
        except msgspec.DecodeError as e:
            # NB. under strict an undecodable/tampered manifest is a trust
            # anomaly (fail-closed), not the silent miss verify/off treat it as.
            if mode == "strict":
                raise CacheSignatureError(
                    "A cache manifest could not be decoded (mode='strict'). "
                    "The cache may be corrupted or was modified outside of "
                    "marimo.\n"
                    "To recover, call cache_clear() on the cached function or "
                    "context manager."
                ) from e
            raise

        # Guard: the manifest must describe the entry we asked for, checked
        # before any blob I/O or deserialization (otherwise it is only caught
        # in cache_attempt() after every blob has already been
        # pickle.loads()-ed). The hash is inside the signed bytes, so under a
        # verifying mode a mismatch is a trust anomaly (a corrupt, misfiled, or
        # substituted manifest): strict surfaces it (fail-closed), while
        # verify/off treat it as a generic miss (recompute).
        if cache_data.hash != key.hash:
            if mode == "strict":
                raise CacheSignatureError(
                    f"A cache manifest's hash {cache_data.hash!r} does not "
                    f"match the requested key {key.hash!r} (mode='strict'). "
                    f"The cache may be corrupted or was modified outside of "
                    f"marimo.\n"
                    f"To recover, call cache_clear() on the cached function or "
                    f"context manager."
                )
            raise FileNotFoundError(
                f"Cache manifest hash {cache_data.hash!r} does not match the "
                f"requested key {key.hash!r}"
            )

        # Manifest verification (synchronous, before any blob I/O). Returns the
        # signer that validated the manifest (which enables blob-hash checking
        # below), or None in 'off' mode. Raises CacheSignatureError when a
        # verify/strict loader cannot verify the entry — load_cache then misses
        # (verify) or re-raises (strict).
        effective_signer = self._resolve_effective_signer(cache_data, mode)

        base = Path(self.name) / cache_data.hash
        blob_hash_map = cache_data.meta.blob_hashes  # {} for unsigned entries

        # Collect references to load
        ref_vars: dict[str, str] = {}
        ref_type_hints: dict[str, str | None] = {}
        variable_hashes: dict[str, str] = {}
        # Instances of cell-defined (__main__) classes are deferred: their
        # class must be re-exec'd into __main__ before the blob can unpickle.
        deferred: dict[str, tuple[str, str]] = {}
        # Defs whose blob we skip fetching because the value can't be
        # materialized here anyway (its module is absent). Maps to the
        # type_hint so the `UnhashableStub` can name what it stood in for.
        unresolvable: dict[str, str | None] = {}
        for var_name, item in cache_data.defs.items():
            if var_name in cache_data.ui_defs:
                ref_vars[var_name] = (base / "ui.pickle").as_posix()
            elif item.reference is not None:
                if item.type_hint and item.type_hint.startswith("__main__."):
                    deferred[var_name] = (
                        item.reference,
                        item.type_hint.rsplit(".", 1)[-1],
                    )
                elif not _module_available(item.type_hint):
                    unresolvable[var_name] = item.type_hint
                else:
                    ref_vars[var_name] = item.reference
                    ref_type_hints[item.reference] = item.type_hint
            if item.hash:
                variable_hashes[var_name] = item.hash

        # Eagerly resolve return value reference alongside defs
        return_ref: str | None = None
        return_type_hint: str | None = None
        if (
            cache_data.meta.return_value
            and cache_data.meta.return_value.reference
        ):
            return_ref = cache_data.meta.return_value.reference
            return_type_hint = cache_data.meta.return_value.type_hint

        unique_keys = set(ref_vars.values())
        if return_ref:
            unique_keys.add(return_ref)
        unpickled = self._read_blobs(
            unique_keys,
            ref_type_hints,
            return_ref,
            return_type_hint,
            blob_hash_map,
            effective_signer,
        )

        # Distribute to defs
        defs: dict[str, Any] = {}
        for var_name, item in cache_data.defs.items():
            if var_name in unresolvable:
                # Module absent, blob never fetched — stand in an
                # `UnhashableStub` carrying the persisted digest so a consumer
                # reproduces its key.
                defs[var_name] = UnhashableStub(
                    var_name=var_name,
                    type_name=unresolvable[var_name],
                    content_hash=variable_hashes.get(var_name, ""),
                )
            elif var_name in deferred:
                ref, requires = deferred[var_name]
                # Read the bytes now (via this loader's store); defer only
                # the unpickle until Cache.restore has materialized the class.
                raw = self.store.get(ref)
                if not raw:
                    raise _incomplete_cache_error(effective_signer)
                # Deferred blobs bypass `_read_blobs`, so verify the signed
                # blob hash here too — before these bytes are ever unpickled
                # by `ReferenceStub.load` during `Cache.restore`.
                _verify_signed_blob(ref, raw, blob_hash_map, effective_signer)
                stub = ImmediateReferenceStub(
                    ReferenceStub(ref, hash_value=item.hash or "", blob=raw)
                )
                # Tag the cell class this instance needs materialized first.
                stub.requires = requires
                defs[var_name] = stub
            elif var_name in ref_vars:
                ref_key = ref_vars[var_name]
                val = unpickled.get(ref_key)
                if var_name in cache_data.ui_defs and isinstance(val, dict):
                    defs[var_name] = val[var_name]
                elif isinstance(val, UnhashableStub):
                    # NB. carry the persisted digest so a consumer reproduces
                    # its key without the value.
                    defs[var_name] = UnhashableStub(
                        var_name=var_name,
                        type_name=val.type_name,
                        error_msg=val.error_msg,
                        content_hash=variable_hashes.get(var_name, ""),
                    )
                else:
                    defs[var_name] = val
            else:
                defs[var_name] = from_item(item, var_name)

        if return_ref and return_ref in unpickled:
            return_item = unpickled[return_ref]
        elif cache_data.meta.return_value:
            return_item = from_item(cache_data.meta.return_value, "return")
        else:
            return_item = None

        return Cache(
            hash=cache_data.hash,
            cache_type=cache_data.cache_type.value,
            stateful_refs=set(cache_data.stateful_refs),
            defs=defs,
            meta={
                "version": cache_data.meta.version or MARIMO_CACHE_VERSION,
                "return": return_item,
                "variable_hashes": variable_hashes,
            },
            hit=True,
        )

    def _deserialize_blob(
        self,
        key: str,
        data: bytes,
        ref_type_hints: dict[str, str | None],
        return_ref: str | None,
        return_type_hint: str | None,
        blob_hash_map: dict[str, str] | None = None,
        effective_signer: CacheSigner | None = None,
    ) -> Any:
        # Verify the blob hash before deserialization so a tampered blob never
        # reaches pickle.loads. Raises CacheSignatureError (propagated by the
        # callers) on mismatch or a missing hash under a verified manifest.
        _verify_signed_blob(key, data, blob_hash_map, effective_signer)
        ext = Path(key).suffix
        deserialize = BLOB_DESERIALIZERS.get(
            ext, BLOB_DESERIALIZERS[".pickle"]
        )
        type_hint = ref_type_hints.get(key) or (
            return_type_hint if key == return_ref else None
        )
        try:
            return deserialize(data, type_hint)
        except ModuleNotFoundError as e:
            # Raise if we need something for return, otherwise defer to a stub.
            if key == return_ref:
                raise
            return UnhashableStub(error_msg=str(e), type_name=type_hint)

    def _read_blobs(
        self,
        unique_keys: set[str],
        ref_type_hints: dict[str, str | None],
        return_ref: str | None,
        return_type_hint: str | None,
        blob_hash_map: dict[str, str] | None = None,
        effective_signer: CacheSigner | None = None,
    ) -> dict[str, Any]:
        """Read + deserialize blobs in parallel via threads."""
        results: queue.Queue[tuple[str, Any]] = queue.Queue()
        # Threads append here on a signed-hash mismatch. list.append is
        # thread-safe under the GIL. Surfaced as the first error after join so
        # a strict-mode loader raises rather than degrading to a
        # generic cache miss.
        errors: list[CacheSignatureError] = []

        def _load_blob(key: str) -> None:
            try:
                data = self.store.get(key)
                if data:
                    results.put(
                        (
                            key,
                            self._deserialize_blob(
                                key,
                                data,
                                ref_type_hints,
                                return_ref,
                                return_type_hint,
                                blob_hash_map,
                                effective_signer,
                            ),
                        )
                    )
                else:
                    results.put((key, _BlobStatus.MISSING))
            except CacheSignatureError as exc:
                errors.append(exc)
                results.put((key, _BlobStatus.MISSING))
            except Exception as e:
                # Hash verification precedes deserialization, so bytes that
                # reach here are authentic — a failure is an environment issue,
                # not tampering. Recompute rather than flag corruption.
                LOGGER.warning("Failed to deserialize blob %s: %s", key, e)
                results.put((key, _BlobStatus.UNREADABLE))

        threads = [
            threading.Thread(target=_load_blob, args=(key,))
            for key in unique_keys
        ]
        for t in threads:
            t.start()
        unpickled: dict[str, Any] = {}
        missing = False
        unreadable = False
        try:
            # Drain all N results (one per key) and join before deciding.
            # Raising on the first MISSING dequeued would let a genuinely
            # missing blob mask a concurrent thread's signed-hash mismatch,
            # routing a strict loader through the generic-miss path instead of
            # raising. Each error thread appends to `errors` before putting its
            # MISSING, so after the full drain `errors` is complete.
            for _ in unique_keys:
                key, val = results.get()
                if val is _BlobStatus.MISSING:
                    missing = True
                elif val is _BlobStatus.UNREADABLE:
                    unreadable = True
                else:
                    unpickled[key] = val
        finally:
            for t in threads:
                t.join()
        # Precedence: a hash mismatch or a genuinely-missing blob under a
        # verified manifest is a trust anomaly (strict raises); an
        # authentic-but-unreadable blob is a plain miss (recompute) in every
        # mode, matching the deserializers' documented recompute fallback.
        if errors:
            raise errors[0]
        if missing:
            raise _incomplete_cache_error(effective_signer)
        if unreadable:
            raise FileNotFoundError(
                "Incomplete cache: a blob could not be deserialized"
            )
        return unpickled

    def save_cache(self, cache: Cache) -> bool:
        # Reap completed threads
        self._pending = [t for t in self._pending if t.is_alive()]

        # Fresh load, so invalidate the "stale" marker.
        _cache_state().stale_keys.discard(str(self.build_path(cache.key)))

        path = Path(self.name) / cache.hash
        # Copy so per-def digests below don't mutate the cache's meta.
        variable_hashes = dict(cache.meta.get("variable_hashes", {}))
        return_item = to_item(
            path, cache.meta.get("return", None), var_name="return"
        )
        if return_item.reference:
            # Normalize base name to "return" while preserving format extension.
            ext = Path(return_item.reference).suffix
            return_item.reference = (path / f"return{ext}").as_posix()

        try:
            cache_type_enum = CacheType(cache.cache_type)
        except ValueError:
            cache_type_enum = CacheType.UNKNOWN

        # Separate vars by loader strategy
        format_vars: dict[str, dict[str, Any]] = {}  # loader → {var: obj}
        ui_vars: dict[str, Any] = {}
        defs_dict: dict[str, Item] = {}
        ui_defs_list: list[str] = []

        for var, obj in cache.defs.items():
            if var not in variable_hashes:
                # NB. persist a digest for data primitives so a consumer
                # reproduces its key without the value.
                digest = _maybe_content_digest(obj)
                if digest:
                    variable_hashes[var] = digest
            loader = maybe_update_lazy_stub(obj)
            item = to_item(
                path,
                obj,
                var_name=var,
                loader=loader,
                hash=variable_hashes.get(var, ""),
            )
            defs_dict[var] = item
            if item.import_ref is not None:
                # Re-importable reference: lives inline in the manifest,
                # no blob to write.
                continue
            if loader == "ui":
                ui_vars[var] = obj
                ui_defs_list.append(var)
            elif loader not in ("inline",):
                format_vars.setdefault(loader, {})[var] = obj

        version = cache.meta.get("version", MARIMO_CACHE_VERSION)

        # Use property to normalise any stale _Unset sentinel.
        signer = self.signer
        mode = self._effective_mode()
        # Sign only when verifying: 'off' writes unsigned (legacy), and a
        # signer without a private key can't sign at all.
        signing = mode != "off" and signer is not None and signer.can_sign

        if mode != "off" and not signing:
            # NB. skip rather than write: an unsigned entry only pollutes the
            # store with data every verifying reader rejects on load.
            if not self._write_skip_warned:
                self._write_skip_warned = True
                LOGGER.warning(
                    "LazyLoader mode=%r cannot sign cache entries (no private "
                    "signing key is available), so this write was skipped — an "
                    "unsigned entry would be rejected on load. Install "
                    "'cryptography' and set MARIMO_CACHE_SIGNING_PRIVATE_KEY "
                    "(or pass a private-key signer) to write signed entries, or "
                    "use mode='off' to write unsigned.",
                    mode,
                )
            return False

        # Blob digests collected while writing; embedded + signed by
        # `_encode_manifest` on the signed path (stays empty otherwise).
        blob_hashes: dict[str, str] = {}

        def _encode_manifest() -> bytes:
            # Encoded after the blobs so any `unserializable_type` marks set
            # by `_put_or_mark_unserializable` are reflected in the manifest,
            # and (when signing) every blob hash has been collected.
            if signing:
                assert signer is not None
                base_schema = CacheSchema(
                    hash=cache.hash,
                    cache_type=cache_type_enum,
                    stateful_refs=list(cache.stateful_refs),
                    defs=defs_dict,
                    meta=Meta(
                        version=version,
                        return_value=return_item,
                        blob_hashes=blob_hashes,
                        signer_public_key=signer.public_key_pem(),
                        signature=None,
                    ),
                    ui_defs=ui_defs_list,
                )
                sig = signer.sign(_signable_bytes(base_schema))
                signed_meta = msgspec.structs.replace(
                    base_schema.meta, signature=sig
                )
                return msgspec.json.encode(
                    msgspec.structs.replace(base_schema, meta=signed_meta)
                )
            return msgspec.json.encode(
                CacheSchema(
                    hash=cache.hash,
                    cache_type=cache_type_enum,
                    stateful_refs=list(cache.stateful_refs),
                    defs=defs_dict,
                    meta=Meta(
                        version=version,
                        return_value=return_item,
                    ),
                    ui_defs=ui_defs_list,
                )
            )

        # Capture values for the background thread
        store = self.store
        return_ref = return_item.reference
        return_value = cache.meta.get("return", None)
        return_loader = (
            maybe_update_lazy_stub(return_value)
            if return_value is not None
            else "pickle"
        )
        manifest_key = str(self.build_path(cache.key))

        def _put_or_mark_unserializable(
            key: str,
            value: Any,
            serialize: Callable[[Any], bytes],
            items: list[Item],
            var_name: str = "",
        ) -> bool:
            """Store one blob; on serialization failure write no blob and
            instead mark each manifest `Item` with `unserializable_type`.

            Returns `True` when the blob was stored, `False` when it was
            marked unserializable. Records the blob digest for the signed
            manifest when the loader is signing.
            """
            try:
                data = serialize(value)
                store.put(key, data)
                if signing:
                    blob_hashes[key] = _sha256hex(data)
            except Exception as e:
                LOGGER.warning(
                    "Failed to serialize %s for cache; marking "
                    "unserializable: %s",
                    var_name or key,
                    e,
                )
                fallback = f"{type(value).__module__}.{type(value).__name__}"
                for item in items:
                    type_name = item.type_hint or fallback
                    item.reference = None
                    # NB. keep item.hash — the content digest stays valid even
                    # when the value blob can't be pickled.
                    item.type_hint = None
                    item.unserializable_type = type_name
                return False
            return True

        def _serialize_and_write() -> None:
            """Serialize and write all blobs + manifest in background."""
            try:
                if return_ref:
                    serialize = BLOB_SERIALIZERS.get(
                        return_loader, pickle.dumps
                    )
                    _put_or_mark_unserializable(
                        return_ref,
                        return_value,
                        serialize,
                        [return_item],
                        "return",
                    )
                if ui_vars:
                    ui_key = (path / "ui.pickle").as_posix()
                    ui_ok = _put_or_mark_unserializable(
                        ui_key,
                        ui_vars,
                        pickle.dumps,
                        [defs_dict[v] for v in ui_defs_list],
                        "ui",
                    )
                    if not ui_ok:
                        # UI defs restore via `ui_defs` → `ui.pickle`,
                        # bypassing the per-Item marks. Drop them from
                        # `ui_defs` so restore routes through the now-marked
                        # Items instead, and clear any stale blob lingering
                        # from a prior run at this same hash path (which would
                        # otherwise load as a phantom hit).
                        ui_defs_list.clear()
                        try:
                            store.clear(ui_key)
                        except Exception:
                            LOGGER.warning(
                                "Failed to clear stale ui blob %s", ui_key
                            )
                for loader, vars_dict in format_vars.items():
                    serialize = BLOB_SERIALIZERS.get(loader, pickle.dumps)
                    for var, obj in vars_dict.items():
                        _put_or_mark_unserializable(
                            (path / f"{var}.{loader}").as_posix(),
                            obj,
                            serialize,
                            [defs_dict[var]],
                            var,
                        )
                # Manifest last — readers check for it to detect complete
                # writes, and it now carries any unserializable marks set above
                # plus (when signing) the signed blob hashes and signature.
                store.put(manifest_key, _encode_manifest())
            except Exception:
                LOGGER.exception("Failed to write cache blobs for %s", path)

        self._dispatch_write(_serialize_and_write)
        return True

    def _dispatch_write(self, write_fn: Callable[[], None]) -> None:
        """Run the blob+manifest write on a background thread (native)."""
        t = threading.Thread(target=write_fn, daemon=False)
        t.start()
        self._pending.append(t)

    def to_blob(self, cache: Cache) -> bytes | None:
        # Not used — save_cache is overridden. Kept for interface compliance.
        del cache
        return None


class WasmLazyLoader(LazyLoader):
    """WASM variant of `LazyLoader`, selected once via the dual-loader
    registry (so the environment is never re-checked below)."""

    _store_cls = WasmLazyStore

    def _read_blobs(
        self,
        unique_keys: set[str],
        ref_type_hints: dict[str, str | None],
        return_ref: str | None,
        return_type_hint: str | None,
        blob_hash_map: dict[str, str] | None = None,
        effective_signer: CacheSigner | None = None,
    ) -> dict[str, Any]:
        unpickled: dict[str, Any] = {}
        # The store handles concurrency (HTTP batch fetch in WASM). The WASM
        # variant pairs with a `WasmLazyStore` (see `_store_cls`), whose
        # `get_batch` fetches concurrently; `get_batch` is defined on every
        # `Store` so no narrowing is needed. A signed-hash mismatch raises
        # CacheSignatureError straight out of `_deserialize_blob`.
        for key, data in self.store.get_batch(unique_keys):
            if not data:
                raise _incomplete_cache_error(effective_signer)
            unpickled[key] = self._deserialize_blob(
                key,
                data,
                ref_type_hints,
                return_ref,
                return_type_hint,
                blob_hash_map,
                effective_signer,
            )
        return unpickled

    def _dispatch_write(self, write_fn: Callable[[], None]) -> None:
        write_fn()  # synchronous — no threads in Pyodide

    def _on_restore_failure(
        self, key: HashKey, manifest_blob: bytes | None
    ) -> None:
        manifest_path = str(self.build_path(key))
        blob_keys: list[str] = []
        if manifest_blob:
            try:
                cache_data = msgspec.json.decode(
                    manifest_blob, type=CacheSchema
                )
                for item in cache_data.defs.values():
                    if item.reference:
                        blob_keys.append(item.reference)
                if cache_data.meta.return_value and (
                    ref := cache_data.meta.return_value.reference
                ):
                    blob_keys.append(ref)
            except Exception:
                pass
        poisoned = _cache_state().poisoned_keys
        self.store.clear(manifest_path)
        poisoned.add(manifest_path)
        for blob_key in blob_keys:
            self.store.clear(blob_key)
            poisoned.add(blob_key)
