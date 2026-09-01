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


def test_workspace_marimo_toml_store_never_reaches_the_loader(
    monkeypatch, tmp_path
) -> None:
    """End-to-end: a committed `.marimo.toml` cannot choose the pickle store.

    A store set there loads as the *user* layer, so it never shows up in the
    config overrides that `cache_store_is_untrusted` inspects. Stripping it at
    the config layer is what keeps it away from an unverified `pickle.loads`;
    without that, this store would be treated as operator-chosen.
    """
    from marimo._config.manager import UserConfigManager
    from marimo._save.stores import cache_store_is_untrusted, get_store

    workspace_config = tmp_path / ".marimo.toml"
    workspace_config.write_text(
        '[cache.store]\ntype = "file"\nargs = { save_path = "/tmp/attacker" }\n'
    )
    monkeypatch.setattr(
        "marimo._config.manager.get_or_create_user_config_path",
        lambda: str(workspace_config),
    )
    monkeypatch.setattr(
        "marimo._config.manager.is_trusted_user_config_path",
        lambda _path: False,
    )

    # Stripped at the config layer, so nothing downstream has to identify it.
    config = UserConfigManager().get_config(hide_secrets=False)
    assert config.get("cache", {}).get("store") is None

    # Note it is *not* reachable as an "untrusted override" either, because the
    # user layer is not an override — which is exactly why stripping is needed.
    assert cache_store_is_untrusted(str(tmp_path)) is False

    # Store selection falls back to the default rather than the named path.
    store = get_store(str(tmp_path))
    assert isinstance(store, DEFAULT_STORE)
    assert "attacker" not in str(getattr(store, "save_path", ""))
