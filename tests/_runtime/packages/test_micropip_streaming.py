# Copyright 2026 Marimo. All rights reserved.
"""Unit tests for the marimo-free `stream_transaction_install` engine.

micropip itself only runs inside Pyodide, so we monkeypatch
`micropip._micropip` + `micropip.transaction.Transaction` with stubs that
simulate the resolution / install steps deterministically.
"""

from __future__ import annotations

import asyncio
import sys
import types
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest


@dataclass
class _FakeWheel:
    name: str
    install_error: Exception | None = None
    install_event: asyncio.Event | None = None

    async def install(self, _wheel_base: Any, _compat: Any) -> None:
        if self.install_event is not None:
            await self.install_event.wait()
        if self.install_error is not None:
            raise self.install_error


@dataclass
class _FakeTransaction:
    wheels: list[_FakeWheel] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    pyodide_packages: list[tuple[str, str, str]] = field(default_factory=list)
    seen_requirements: list[str] = field(default_factory=list)
    init_kwargs: dict[str, Any] = field(default_factory=dict)

    async def gather_requirements(self, requirements: list[str]) -> None:
        self.seen_requirements.extend(requirements)


class _FakeCompatLayer:
    def __init__(self) -> None:
        self.loaded: list[list[str]] = []

    def to_js(self, value: Any) -> Any:
        return value

    async def loadPackage(self, names: list[str]) -> None:
        self.loaded.append(list(names))


@dataclass
class _FakeMicropipManager:
    compat_layer: _FakeCompatLayer = field(default_factory=_FakeCompatLayer)
    index_urls: list[str] = field(default_factory=lambda: ["https://default/"])
    constraints: list[str] = field(default_factory=list)


def _install_fake_micropip(
    monkeypatch: Any, fake_tx: _FakeTransaction
) -> _FakeMicropipManager:
    """Install fake `micropip`, `micropip._utils`, `micropip.transaction`, and
    `packaging.utils` modules into sys.modules so the engine resolves to them.
    """
    fake_mgr = _FakeMicropipManager()

    micropip_mod = types.ModuleType("micropip")
    micropip_mod._micropip = fake_mgr  # type: ignore[attr-defined]

    utils_mod = types.ModuleType("micropip._utils")
    utils_mod.default_environment = dict  # type: ignore[attr-defined]

    txn_mod = types.ModuleType("micropip.transaction")

    def _Transaction(**kwargs: Any) -> _FakeTransaction:
        fake_tx.init_kwargs = kwargs
        return fake_tx

    txn_mod.Transaction = _Transaction  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "micropip", micropip_mod)
    monkeypatch.setitem(sys.modules, "micropip._utils", utils_mod)
    monkeypatch.setitem(sys.modules, "micropip.transaction", txn_mod)
    return fake_mgr


async def _drain(agen: Any) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    async for item in agen:
        out.append(item)
    return out


async def test_two_wheels_both_succeed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    tx = _FakeTransaction(wheels=[_FakeWheel("foo"), _FakeWheel("bar")])
    _install_fake_micropip(monkeypatch, tx)

    results = await _drain(stream_transaction_install(["foo", "bar"]))
    assert sorted(results) == [("bar", True), ("foo", True)]


async def test_wheel_install_failure_no_double_yield(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    tx = _FakeTransaction(
        wheels=[
            _FakeWheel("foo", install_error=RuntimeError("boom")),
            _FakeWheel("bar"),
        ]
    )
    _install_fake_micropip(monkeypatch, tx)

    results = await _drain(stream_transaction_install(["foo", "bar"]))
    assert sorted(results) == [("bar", True), ("foo", False)]
    # Each requested package yields exactly once.
    assert [name for name, _ in results].count("foo") == 1


async def test_resolution_failure_yields_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    tx = _FakeTransaction(failed=["foo"])
    _install_fake_micropip(monkeypatch, tx)

    results = await _drain(stream_transaction_install(["foo"]))
    assert results == [("foo", False)]


async def test_pyodide_package_only_loadpackage_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    tx = _FakeTransaction(
        pyodide_packages=[("numpy", "1.26.0", "default")],
    )
    fake_mgr = _install_fake_micropip(monkeypatch, tx)

    results = await _drain(stream_transaction_install(["numpy"]))
    assert results == [("numpy", True)]
    assert fake_mgr.compat_layer.loaded == [["numpy"]]


async def test_index_urls_override_passed_to_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    tx = _FakeTransaction(wheels=[_FakeWheel("foo")])
    fake_mgr = _install_fake_micropip(monkeypatch, tx)

    override = ["https://my.private/simple", "https://extra/simple"]
    await _drain(stream_transaction_install(["foo"], index_urls=override))
    assert tx.init_kwargs["index_urls"] == override
    # And the singleton's was NOT used.
    assert tx.init_kwargs["index_urls"] is not fake_mgr.index_urls


async def test_index_urls_none_falls_back_to_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    tx = _FakeTransaction(wheels=[_FakeWheel("foo")])
    fake_mgr = _install_fake_micropip(monkeypatch, tx)

    await _drain(stream_transaction_install(["foo"], index_urls=None))
    assert tx.init_kwargs["index_urls"] is fake_mgr.index_urls


async def test_url_spec_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """PEP 508 URL specs in the packages list must reach gather_requirements
    unaltered — the engine shouldn't try to be clever about them."""
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    tx = _FakeTransaction(wheels=[_FakeWheel("foo")])
    _install_fake_micropip(monkeypatch, tx)

    spec = "foo @ git+https://example.com/repo@deadbeef"
    await _drain(stream_transaction_install([spec]))
    assert spec in tx.seen_requirements


async def test_versions_appended(monkeypatch: pytest.MonkeyPatch) -> None:
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    tx = _FakeTransaction(wheels=[_FakeWheel("foo")])
    _install_fake_micropip(monkeypatch, tx)

    await _drain(
        stream_transaction_install(["foo"], versions={"foo": "1.2.3"})
    )
    assert "foo==1.2.3" in tx.seen_requirements


async def test_streaming_order_first_done_first_yielded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The engine should yield as each wheel completes, not in submission order."""
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    fast_done = asyncio.Event()
    slow_done = asyncio.Event()
    tx = _FakeTransaction(
        wheels=[
            _FakeWheel("slow", install_event=slow_done),
            _FakeWheel("fast", install_event=fast_done),
        ]
    )
    _install_fake_micropip(monkeypatch, tx)

    async def driver() -> list[tuple[str, bool]]:
        results: list[tuple[str, bool]] = []
        agen = stream_transaction_install(["slow", "fast"])
        # Let `fast` finish first.
        fast_done.set()
        async for item in agen:
            results.append(item)
            if item[0] == "fast":
                # Now release `slow` so the generator can complete.
                slow_done.set()
        return results

    results = await driver()
    assert results[0] == ("fast", True)
    assert results[1] == ("slow", True)


async def test_versioned_spec_tracked_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A versioned spec ("foo==1.0") must be tracked by its base name so the
    wheel install ("foo") is recognized as fulfilling the request."""
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    tx = _FakeTransaction(wheels=[_FakeWheel("foo")])
    _install_fake_micropip(monkeypatch, tx)

    results = await _drain(stream_transaction_install(["foo==1.0"]))
    # Yields the original spec string, not the bare name.
    assert results == [("foo==1.0", True)]


async def test_url_spec_tracked_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PEP 508 URL spec ("foo @ git+…") must be tracked by base name too."""
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    tx = _FakeTransaction(wheels=[_FakeWheel("foo")])
    _install_fake_micropip(monkeypatch, tx)

    spec = "foo @ git+https://example.com/repo@deadbeef"
    results = await _drain(stream_transaction_install([spec]))
    assert results == [(spec, True)]


async def test_loadpackage_failure_yields_false_no_terminate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A loadPackage exception must yield (name, False) per pyodide package
    rather than crashing the generator mid-stream."""
    from marimo._runtime.packages._micropip_streaming import (
        stream_transaction_install,
    )

    class _BadCompatLayer(_FakeCompatLayer):
        async def loadPackage(self, names: list[str]) -> None:
            del names
            raise RuntimeError("pyodide load failed")

    fake_mgr = _FakeMicropipManager(compat_layer=_BadCompatLayer())
    tx = _FakeTransaction(
        wheels=[_FakeWheel("foo")],
        pyodide_packages=[("numpy", "1.26.0", "default")],
    )

    micropip_mod = types.ModuleType("micropip")
    micropip_mod._micropip = fake_mgr  # type: ignore[attr-defined]
    utils_mod = types.ModuleType("micropip._utils")
    utils_mod.default_environment = dict  # type: ignore[attr-defined]
    txn_mod = types.ModuleType("micropip.transaction")

    def _Transaction(**kwargs: Any) -> _FakeTransaction:
        tx.init_kwargs = kwargs
        return tx

    txn_mod.Transaction = _Transaction  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "micropip", micropip_mod)
    monkeypatch.setitem(sys.modules, "micropip._utils", utils_mod)
    monkeypatch.setitem(sys.modules, "micropip.transaction", txn_mod)

    results = await _drain(stream_transaction_install(["foo", "numpy"]))
    # Generator completed (no crash); numpy yielded False from the failure.
    assert ("numpy", False) in results
    # foo wheel still succeeded independently.
    assert ("foo", True) in results
