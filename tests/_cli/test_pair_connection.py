# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import json
import os
from typing import TYPE_CHECKING

import pytest

from marimo._cli.pair.client import PairInputError
from marimo._cli.pair.connection import (
    ConnectionStore,
    participant_id,
    resolve_identity,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_participant_id_uses_the_approved_tuple() -> None:
    identity = resolve_identity(
        {
            "MARIMO_PAIR_HARNESS": "claude",
            "MARIMO_PAIR_CONVERSATION_ID": "conversation-1",
        },
        harness_name="Claude Code",
    )
    values = [
        "marimo-participant-v1",
        "session-1",
        "claude",
        "conversation",
        "conversation-1",
    ]
    expected = hashlib.sha256(
        json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()

    assert participant_id("session-1", identity) == f"p1_{expected}"
    assert identity.scope == "conversation"
    assert identity.harness.display_name == "Claude Code"


def test_fallback_identity_is_shared_and_repeatable() -> None:
    first = resolve_identity({}, harness_id="pi", harness_name="Pi")
    second = resolve_identity({}, harness_id="pi", harness_name="Pi")

    assert first.scope == "harness"
    assert first.conversation_id is None
    assert participant_id("session-1", first) == participant_id(
        "session-1", second
    )
    assert participant_id("session-1", first) != participant_id(
        "session-2", first
    )


def test_advisory_name_requires_harness_id() -> None:
    with pytest.raises(PairInputError, match="--harness-name requires"):
        resolve_identity({}, harness_name="Pi")


@pytest.mark.parametrize(
    "environ",
    [
        {"MARIMO_PAIR_HARNESS": "claude"},
        {"MARIMO_PAIR_CONVERSATION_ID": "conversation-1"},
        {
            "MARIMO_PAIR_HARNESS": "claude",
            "MARIMO_PAIR_CONVERSATION_ID": " ",
        },
    ],
)
def test_incomplete_override_pair_fails(environ: dict[str, str]) -> None:
    with pytest.raises(PairInputError, match="Set both"):
        resolve_identity(environ)


def test_connection_file_excludes_raw_conversation_and_token(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    store = ConnectionStore(root)
    identity = resolve_identity(
        {
            "MARIMO_PAIR_HARNESS": "claude",
            "MARIMO_PAIR_CONVERSATION_ID": "private-conversation-id",
        },
        harness_name="Claude Code",
    )
    selected = store.save(
        url="https://user:pass@EXAMPLE.com/base/?token=secret#fragment",
        stable_session_id="session-1",
        identity=identity,
        participant=participant_id("session-1", identity),
    )
    raw = selected.path.read_text(encoding="utf-8")

    assert "private-conversation-id" not in raw
    assert "secret" not in raw
    assert "pass" not in raw
    assert json.loads(raw)["stableSessionId"] == "session-1"
    assert json.loads(raw)["scope"] == "conversation"
    assert (
        store.load(
            url="https://example.com/base",
            stable_session_id="session-1",
            identity=identity,
        )
        == selected
    )
    assert not list(root.glob("*.tmp"))
    if os.name == "posix":
        assert root.stat().st_mode & 0o777 == 0o700
        assert selected.path.stat().st_mode & 0o777 == 0o600


def test_generic_lookup_finds_one_advisory_harness_binding(
    tmp_path: Path,
) -> None:
    store = ConnectionStore(tmp_path)
    pi = resolve_identity({}, harness_id="pi", harness_name="Pi")
    saved = store.save(
        url="http://localhost:2718",
        stable_session_id="session-1",
        identity=pi,
        participant=participant_id("session-1", pi),
    )

    selected = store.load(
        url="http://localhost:2718",
        stable_session_id="session-1",
        identity=resolve_identity({}),
    )

    assert selected == saved
    assert (
        store.load(
            url="http://localhost:2718",
            stable_session_id="session-2",
            identity=resolve_identity({}),
        )
        is None
    )


def test_generic_lookup_rejects_ambiguous_bindings(
    tmp_path: Path,
) -> None:
    store = ConnectionStore(tmp_path)
    for harness_id in ("pi", "opencode"):
        identity = resolve_identity({}, harness_id=harness_id)
        store.save(
            url="http://localhost:2718",
            stable_session_id="session-1",
            identity=identity,
            participant=participant_id("session-1", identity),
        )

    with pytest.raises(PairInputError, match="Several Pair connections"):
        store.load(
            url="http://localhost:2718",
            stable_session_id="session-1",
            identity=resolve_identity({}),
        )


def test_conversation_lookup_selects_only_its_own_binding(
    tmp_path: Path,
) -> None:
    store = ConnectionStore(tmp_path)
    first = resolve_identity(
        {
            "MARIMO_PAIR_HARNESS": "claude",
            "MARIMO_PAIR_CONVERSATION_ID": "first",
        }
    )
    second = resolve_identity(
        {
            "MARIMO_PAIR_HARNESS": "claude",
            "MARIMO_PAIR_CONVERSATION_ID": "second",
        }
    )
    saved = store.save(
        url="http://localhost:2718",
        stable_session_id="session-1",
        identity=first,
        participant=participant_id("session-1", first),
    )

    assert (
        store.load(
            url="http://localhost:2718",
            stable_session_id="session-1",
            identity=first,
        )
        == saved
    )
    assert (
        store.load(
            url="http://localhost:2718",
            stable_session_id="session-1",
            identity=second,
        )
        is None
    )


def test_corrupt_file_requires_connect_but_connect_can_replace_it(
    tmp_path: Path,
) -> None:
    store = ConnectionStore(tmp_path)
    identity = resolve_identity({})
    selected = store.save(
        url="http://localhost:2718",
        stable_session_id="session-1",
        identity=identity,
        participant=participant_id("session-1", identity),
    )
    selected.path.write_text("not json", encoding="utf-8")

    with pytest.raises(PairInputError, match="file is invalid"):
        store.load(
            url="http://localhost:2718",
            stable_session_id="session-1",
            identity=identity,
        )
    replaced = store.save(
        url="http://localhost:2718",
        stable_session_id="session-1",
        identity=identity,
        participant=participant_id("session-1", identity),
    )
    assert (
        replaced.connection.participant_id
        == selected.connection.participant_id
    )
