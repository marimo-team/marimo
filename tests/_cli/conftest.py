# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_configured_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the default cache resolution.

    A developer's own marimo.toml can pick a cache store, which replaces
    resolution for every cache command under test.
    """
    from marimo._save import stores

    monkeypatch.setattr(
        stores,
        "configured_cache_store",
        lambda current_path=None: None,  # noqa: ARG005
    )
    monkeypatch.setattr(
        stores,
        "cache_store_is_untrusted",
        lambda current_path=None: False,  # noqa: ARG005
    )
