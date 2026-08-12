# Copyright 2026 Marimo. All rights reserved.
"""The unsigned pickle loader must not be redirected by an untrusted store."""

from __future__ import annotations

import types

from marimo._save.loaders.pickle import PickleLoader
from marimo._save.stores import DEFAULT_STORE
from marimo._save.stores.file import FileStore


def _patch_ctx(monkeypatch, store, untrusted: bool) -> None:
    ctx = types.SimpleNamespace(
        cache=types.SimpleNamespace(
            store=store, store_from_untrusted_origin=untrusted
        )
    )
    # BasePersistenceLoader binds get_context at import; PickleLoader's guard
    # imports it lazily from the source module. Patch both.
    monkeypatch.setattr("marimo._save.loaders.loader.get_context", lambda: ctx)
    monkeypatch.setattr("marimo._runtime.context.get_context", lambda: ctx)


def test_pickle_loader_refuses_untrusted_store(monkeypatch, tmp_path) -> None:
    attacker_store = FileStore(save_path=str(tmp_path / "attacker"))
    _patch_ctx(monkeypatch, attacker_store, untrusted=True)

    loader = PickleLoader("ns")

    # The untrusted-origin store is dropped in favor of the default store, so a
    # cloned repo's [cache].store can't feed pickle.loads.
    assert loader.store is not attacker_store
    assert isinstance(loader.store, DEFAULT_STORE)


def test_pickle_loader_keeps_trusted_store(monkeypatch, tmp_path) -> None:
    user_store = FileStore(save_path=str(tmp_path / "user"))
    _patch_ctx(monkeypatch, user_store, untrusted=False)

    loader = PickleLoader("ns")

    assert loader.store is user_store


def test_pickle_loader_honors_explicit_store(monkeypatch, tmp_path) -> None:
    # An explicitly-passed store is caller code (trusted), honored even if the
    # session's configured store is flagged untrusted.
    ctx_store = FileStore(save_path=str(tmp_path / "attacker"))
    _patch_ctx(monkeypatch, ctx_store, untrusted=True)

    explicit = FileStore(save_path=str(tmp_path / "explicit"))
    loader = PickleLoader("ns", store=explicit)

    assert loader.store is explicit
