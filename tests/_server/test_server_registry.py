# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._server.server_registry import (
    ServerRegistryEntry,
    ServerRegistryWriter,
)

if TYPE_CHECKING:
    from pathlib import Path


def _make_entry(
    *,
    port: int = 2718,
    host: str = "localhost",
    pid: int | None = None,
) -> ServerRegistryEntry:
    return ServerRegistryEntry(
        server_id=f"{host}:{port}",
        pid=pid or os.getpid(),
        host=host,
        port=port,
        base_url="",
        started_at="2026-01-01T00:00:00+00:00",
        version="0.0.0",
    )


def _patch_servers_dir(tmp_path: Path):
    return patch(
        "marimo._server.server_registry._servers_dir",
        return_value=tmp_path,
    )


# --- Writer round-trip ---


def test_round_trip(tmp_path: Path):
    entry = _make_entry()
    with _patch_servers_dir(tmp_path):
        writer = ServerRegistryWriter(entry)
        writer.register()

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data == asdict(entry)

        writer.deregister()
        assert list(tmp_path.glob("*.json")) == []


def test_deregister_is_idempotent(tmp_path: Path):
    entry = _make_entry()
    with _patch_servers_dir(tmp_path):
        writer = ServerRegistryWriter(entry)
        writer.register()
        writer.deregister()
        writer.deregister()  # should not raise
        assert list(tmp_path.glob("*.json")) == []


@pytest.mark.skipif(sys.platform == "win32", reason="Unix file permissions")
def test_file_permissions(tmp_path: Path):
    entry = _make_entry()
    with _patch_servers_dir(tmp_path):
        writer = ServerRegistryWriter(entry)
        writer.register()

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        assert oct(files[0].stat().st_mode & 0o777) == "0o600"

        writer.deregister()


def test_multiple_entries(tmp_path: Path):
    e1 = _make_entry(port=2718)
    e2 = _make_entry(port=2719)
    with _patch_servers_dir(tmp_path):
        w1 = ServerRegistryWriter(e1)
        w2 = ServerRegistryWriter(e2)
        w1.register()
        w2.register()

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 2

        w1.deregister()
        w2.deregister()


# --- from_server ---


def test_from_server():
    entry = ServerRegistryEntry.from_server(
        host="localhost",
        port=2718,
        base_url="",
    )
    assert entry.server_id == "localhost:2718"
    assert entry.pid == os.getpid()
    assert entry.host == "localhost"
    assert entry.port == 2718
    assert entry.base_url == ""
    assert entry.version  # non-empty


def test_from_server_with_base_url():
    entry = ServerRegistryEntry.from_server(
        host="0.0.0.0",
        port=8080,
        base_url="/prefix",
    )
    assert entry.server_id == "0.0.0.0:8080"
    assert entry.base_url == "/prefix"
