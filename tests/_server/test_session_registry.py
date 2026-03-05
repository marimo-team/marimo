# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from marimo._server.session_registry import (
    SessionRegistryEntry,
    SessionRegistryReader,
    SessionRegistryWriter,
    _is_pid_alive,
    create_registry_entry,
)


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


class TestSessionRegistryWriterReader:
    def test_round_trip(self, tmp_path: Path) -> None:
        """Write an entry, read it back, verify fields match."""
        entry = _make_entry()
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path,
        ):
            writer = SessionRegistryWriter(entry)
            writer.register()

            entries = SessionRegistryReader.read_all()
            assert len(entries) == 1
            assert entries[0] == entry

            writer.deregister()
            assert SessionRegistryReader.read_all() == []

    def test_deregister_is_idempotent(self, tmp_path: Path) -> None:
        entry = _make_entry()
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path,
        ):
            writer = SessionRegistryWriter(entry)
            writer.register()
            writer.deregister()
            writer.deregister()  # should not raise
            assert SessionRegistryReader.read_all() == []

    def test_file_permissions(self, tmp_path: Path) -> None:
        entry = _make_entry()
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path,
        ):
            writer = SessionRegistryWriter(entry)
            writer.register()

            files = list(tmp_path.glob("*.json"))
            assert len(files) == 1
            stat = files[0].stat()
            assert oct(stat.st_mode & 0o777) == "0o600"

            writer.deregister()

    def test_multiple_entries(self, tmp_path: Path) -> None:
        e1 = _make_entry(port=2718)
        e2 = _make_entry(port=2719)
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path,
        ):
            w1 = SessionRegistryWriter(e1)
            w2 = SessionRegistryWriter(e2)
            w1.register()
            w2.register()

            entries = SessionRegistryReader.read_all()
            assert len(entries) == 2
            ports = {e.port for e in entries}
            assert ports == {2718, 2719}

            w1.deregister()
            w2.deregister()


class TestStaleEntryCleanup:
    def test_stale_pid_removed(self, tmp_path: Path) -> None:
        """Entries with dead PIDs are cleaned up on read."""
        entry = _make_entry(pid=999999999)  # definitely not alive
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path,
        ):
            # Write directly to bypass PID check in register
            path = tmp_path / "stale.json"
            from dataclasses import asdict

            path.write_text(json.dumps(asdict(entry)))

            entries = SessionRegistryReader.read_all()
            assert len(entries) == 0
            # File should have been removed
            assert not path.exists()

    def test_corrupted_entry_removed(self, tmp_path: Path) -> None:
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path,
        ):
            path = tmp_path / "bad.json"
            path.write_text("not valid json {{{")

            entries = SessionRegistryReader.read_all()
            assert len(entries) == 0
            assert not path.exists()

    def test_missing_fields_removed(self, tmp_path: Path) -> None:
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path,
        ):
            path = tmp_path / "incomplete.json"
            path.write_text(json.dumps({"server_id": "x", "port": 1}))

            entries = SessionRegistryReader.read_all()
            assert len(entries) == 0
            assert not path.exists()


class TestFindBy:
    def test_find_by_port(self, tmp_path: Path) -> None:
        e1 = _make_entry(port=2718)
        e2 = _make_entry(port=2719)
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path,
        ):
            SessionRegistryWriter(e1).register()
            SessionRegistryWriter(e2).register()

            found = SessionRegistryReader.find_by_port(2719)
            assert found is not None
            assert found.port == 2719

            assert SessionRegistryReader.find_by_port(9999) is None

    def test_find_by_server_id(self, tmp_path: Path) -> None:
        entry = _make_entry(port=2718)
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path,
        ):
            SessionRegistryWriter(entry).register()

            found = SessionRegistryReader.find_by_server_id("localhost:2718")
            assert found is not None
            assert found.server_id == "localhost:2718"

            assert SessionRegistryReader.find_by_server_id("nope") is None

    def test_empty_dir(self, tmp_path: Path) -> None:
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path,
        ):
            assert SessionRegistryReader.read_all() == []
            assert SessionRegistryReader.find_by_port(2718) is None

    def test_no_dir(self, tmp_path: Path) -> None:
        with patch(
            "marimo._server.session_registry._sessions_dir",
            return_value=tmp_path / "nonexistent",
        ):
            assert SessionRegistryReader.read_all() == []


class TestIsPidAlive:
    def test_current_process(self) -> None:
        assert _is_pid_alive(os.getpid()) is True

    def test_dead_pid(self) -> None:
        assert _is_pid_alive(999999999) is False


class TestCreateRegistryEntry:
    def test_creates_entry_with_current_pid(self) -> None:
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

    def test_none_notebook_path(self) -> None:
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
