# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._server.session_registry import (
    SessionRegistryEntry,
    SessionRegistryReader,
    SessionRegistryWriter,
    _is_pid_alive,
    create_registry_entry,
)

if TYPE_CHECKING:
    from pathlib import Path


def _make_entry(
    *,
    port: int = 2718,
    host: str = "localhost",
    pid: int | None = None,
    notebook_path: str | None = "notebook.py",
) -> SessionRegistryEntry:
    return SessionRegistryEntry(
        server_id=f"{host}:{port}",
        pid=pid or os.getpid(),
        host=host,
        port=port,
        base_url="",
        auth_token="test-token",
        mode="edit",
        started_at="2026-01-01T00:00:00+00:00",
        notebook_path=notebook_path,
        mcp_enabled=False,
        version="0.0.0",
    )


def _patch_sessions_dir(tmp_path: Path):
    return patch(
        "marimo._server.session_registry._sessions_dir",
        return_value=tmp_path,
    )


# --- Writer / Reader round-trip ---


def test_round_trip(tmp_path: Path):
    entry = _make_entry()
    with _patch_sessions_dir(tmp_path):
        writer = SessionRegistryWriter(entry)
        writer.register()

        entries = SessionRegistryReader.read_all()
        assert len(entries) == 1
        assert entries[0] == entry

        writer.deregister()
        assert SessionRegistryReader.read_all() == []


def test_deregister_is_idempotent(tmp_path: Path):
    entry = _make_entry()
    with _patch_sessions_dir(tmp_path):
        writer = SessionRegistryWriter(entry)
        writer.register()
        writer.deregister()
        writer.deregister()  # should not raise
        assert SessionRegistryReader.read_all() == []


@pytest.mark.skipif(sys.platform == "win32", reason="Unix file permissions")
def test_file_permissions(tmp_path: Path):
    entry = _make_entry()
    with _patch_sessions_dir(tmp_path):
        writer = SessionRegistryWriter(entry)
        writer.register()

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        assert oct(files[0].stat().st_mode & 0o777) == "0o600"

        writer.deregister()


def test_multiple_entries(tmp_path: Path):
    e1 = _make_entry(port=2718)
    e2 = _make_entry(port=2719)
    with _patch_sessions_dir(tmp_path):
        w1 = SessionRegistryWriter(e1)
        w2 = SessionRegistryWriter(e2)
        w1.register()
        w2.register()

        entries = SessionRegistryReader.read_all()
        assert len(entries) == 2
        assert {e.port for e in entries} == {2718, 2719}

        w1.deregister()
        w2.deregister()


# --- Stale entry cleanup ---


def test_stale_pid_removed(tmp_path: Path):
    entry = _make_entry(pid=999999999)
    with _patch_sessions_dir(tmp_path):
        # Write directly to simulate a stale entry from a dead process
        path = tmp_path / "stale.json"
        path.write_text(json.dumps(asdict(entry)))

        assert SessionRegistryReader.read_all() == []
        assert not path.exists()


def test_corrupted_entry_removed(tmp_path: Path):
    with _patch_sessions_dir(tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{")

        assert SessionRegistryReader.read_all() == []
        assert not path.exists()


def test_missing_fields_removed(tmp_path: Path):
    with _patch_sessions_dir(tmp_path):
        path = tmp_path / "incomplete.json"
        path.write_text(json.dumps({"server_id": "x", "port": 1}))

        assert SessionRegistryReader.read_all() == []
        assert not path.exists()


# --- find_by ---


def test_find_by_port(tmp_path: Path):
    e1 = _make_entry(port=2718)
    e2 = _make_entry(port=2719)
    with _patch_sessions_dir(tmp_path):
        SessionRegistryWriter(e1).register()
        SessionRegistryWriter(e2).register()

        found = SessionRegistryReader.find_by_port(2719)
        assert found is not None
        assert found.port == 2719
        assert SessionRegistryReader.find_by_port(9999) is None


def test_find_by_server_id(tmp_path: Path):
    entry = _make_entry(port=2718)
    with _patch_sessions_dir(tmp_path):
        SessionRegistryWriter(entry).register()

        found = SessionRegistryReader.find_by_server_id("localhost:2718")
        assert found is not None
        assert found.server_id == "localhost:2718"
        assert SessionRegistryReader.find_by_server_id("nope") is None


def test_empty_dir(tmp_path: Path):
    with _patch_sessions_dir(tmp_path):
        assert SessionRegistryReader.read_all() == []
        assert SessionRegistryReader.find_by_port(2718) is None


def test_no_dir(tmp_path: Path):
    with _patch_sessions_dir(tmp_path / "nonexistent"):
        assert SessionRegistryReader.read_all() == []


# --- _is_pid_alive ---


def test_current_process_is_alive():
    assert _is_pid_alive(os.getpid()) is True


def test_dead_pid():
    assert _is_pid_alive(999999999) is False


# --- create_registry_entry ---


def test_creates_entry_with_current_pid():
    entry = create_registry_entry(
        host="localhost",
        port=2718,
        base_url="",
        auth_token="tok",
        mode="edit",
        notebook_path="nb.py",
        mcp_enabled=False,
    )
    assert entry.server_id == "localhost:2718"
    assert entry.pid == os.getpid()
    assert entry.notebook_path == "nb.py"
    assert entry.mode == "edit"


def test_none_notebook_path():
    entry = create_registry_entry(
        host="0.0.0.0",
        port=8080,
        base_url="/prefix",
        auth_token="",
        mode="run",
        notebook_path=None,
        mcp_enabled=True,
    )
    assert entry.notebook_path is None
    assert entry.mcp_enabled is True
    assert entry.base_url == "/prefix"
