# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_pair_harness_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # CLI tests must not attach to the conversation running the test suite.
    for key in (
        "CODEX_SESSION_ID",
        "CODEX_THREAD_ID",
        "CLAUDE_PID",
        "CLAUDE_CODE_MESSAGING_SOCKET",
        "CLAUDE_CODE_MESSAGING_TOKEN",
        "OPENCODE",
        "OPENCODE_TERMINAL",
        "OPENCODE_SESSION_ID",
    ):
        monkeypatch.delenv(key, raising=False)


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
