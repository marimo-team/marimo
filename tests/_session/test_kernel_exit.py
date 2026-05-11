# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._session import kernel_exit
from marimo._session.kernel_exit import classify_kernel_exit

if TYPE_CHECKING:
    import pytest


def test_unknown_when_exitcode_none() -> None:
    info = classify_kernel_exit(None)
    assert info.cause == "unknown"
    assert info.exitcode is None


def test_normal_exit() -> None:
    info = classify_kernel_exit(0)
    assert info.cause == "exit"
    assert "code 0" in info.message

    info = classify_kernel_exit(2)
    assert info.cause == "exit"
    assert "code 2" in info.message


def test_segfault() -> None:
    info = classify_kernel_exit(-11)
    assert info.cause == "segfault"
    assert "segmentation" in info.message.lower()


def test_sigkill_without_oom_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    # No cgroup files readable -> SIGKILL but cause not classified as OOM.
    monkeypatch.setattr(kernel_exit, "_read_int", lambda _path: None)
    monkeypatch.setattr(kernel_exit, "_read_kv", lambda _path, _key: None)
    info = classify_kernel_exit(-9)
    assert info.cause == "sigkill"
    assert "SIGKILL" in info.message


def test_sigkill_with_cgroup_oom_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_read_int(path: str) -> int | None:
        if "failcnt" in path:
            return 5
        if "max_usage" in path:
            return 1952 * 1024 * 1024
        return None

    monkeypatch.setattr(kernel_exit, "_read_int", fake_read_int)
    monkeypatch.setattr(kernel_exit, "_read_kv", lambda _path, _key: None)
    monkeypatch.setenv(kernel_exit._MEMORY_LIMIT_ENV, "2048")

    info = classify_kernel_exit(-9)
    assert info.cause == "oom"
    assert "1952 MiB" in info.message
    assert "2048 MiB" in info.message


def test_sigkill_with_cgroup_oom_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_read_int(path: str) -> int | None:
        if path == kernel_exit._CGROUP_V2_PEAK:
            return 100 * 1024 * 1024
        return None

    def fake_read_kv(path: str, key: str) -> int | None:
        if path == kernel_exit._CGROUP_V2_EVENTS and key == "oom_kill":
            return 1
        return None

    monkeypatch.setattr(kernel_exit, "_read_int", fake_read_int)
    monkeypatch.setattr(kernel_exit, "_read_kv", fake_read_kv)
    monkeypatch.delenv(kernel_exit._MEMORY_LIMIT_ENV, raising=False)

    info = classify_kernel_exit(-9)
    assert info.cause == "oom"
    assert "100 MiB" in info.message


def test_other_signal() -> None:
    info = classify_kernel_exit(-15)  # SIGTERM
    assert info.cause == "signal_15"
    assert "signal 15" in info.message
