# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from marimo._environments import script_metadata
from marimo._environments.overlay import RuntimeOverlay
from marimo._environments.sandbox import NotebookSandbox

if TYPE_CHECKING:
    from marimo._environments.sandbox import Backend


@pytest.fixture(params=["uv", "pixi"])
def backend(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Backend:
    if os.name == "nt":
        pytest.skip("Executable script fixtures require POSIX")
    name = request.param
    command = tmp_path / name
    command.write_text(
        f"#!{sys.executable}\n"
        + r"""
import json, os, signal, sys
if '--version' in sys.argv:
    print('uv 0.12.0')
    sys.exit()
if '--help' in sys.argv:
    print('--script')
    sys.exit()
source = sys.argv[sys.argv.index('--script') + 1]
print(json.dumps({'pid': os.getpid(), 'source': source}), file=sys.stderr, flush=True)
signal.pause()
""",
        encoding="utf-8",
    )
    command.chmod(0o755)
    monkeypatch.setenv("UV", str(tmp_path / "uv"))
    monkeypatch.setenv("PATH", str(tmp_path))
    return name


@pytest.fixture
def markdown(tmp_path: Path) -> Path:
    path = tmp_path / "notebook.md"
    path.write_text(
        "---\npyproject: |\n  dependencies = []\n---\n\n# Notebook\n"
    )
    return path


@pytest.mark.timeout(15)
async def test_cancelled_preparation_releases_carrier(
    backend: Backend, markdown: Path
) -> None:
    import psutil

    original = markdown.read_text()  # noqa: ASYNC240
    ready = asyncio.Event()
    command: dict[str, str | int] = {}

    def on_output(line: str) -> None:
        command.update(json.loads(line))
        ready.set()

    sandbox = NotebookSandbox(str(markdown), backend)
    task = asyncio.create_task(
        sandbox.launch_async(
            [], overlay=RuntimeOverlay("marimo"), on_output=on_output
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        carrier = Path(str(command["source"]))
        assert carrier.exists()  # noqa: ASYNC240
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), timeout=5)
        assert not psutil.pid_exists(int(command["pid"]))
        assert not carrier.exists()  # noqa: ASYNC240
        assert markdown.read_text() == original  # noqa: ASYNC240
        assert sandbox.environment is None
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        sandbox.close()


@pytest.mark.timeout(10)
async def test_waiting_for_carrier_lock_is_cancellable(markdown: Path) -> None:
    started = asyncio.Event()

    async def wait_for_carrier() -> None:
        started.set()
        async with script_metadata.materialized_for_environment_async(
            str(markdown)
        ):
            pytest.fail("Acquired a carrier still owned by another operation")

    with script_metadata.materialized_for_environment(str(markdown)) as owner:
        task = asyncio.create_task(wait_for_carrier())
        try:
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), timeout=2)
            assert Path(owner.path).exists()  # noqa: ASYNC240
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    async with script_metadata.materialized_for_environment_async(
        str(markdown)
    ) as next_owner:
        assert next_owner.path == owner.path


@pytest.mark.parametrize("backend", ["uv", "pixi"])
async def test_sync_running_sandbox_retains_active_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str
) -> None:
    from unittest.mock import AsyncMock

    from marimo._environments.backends import (
        PixiBackendAdapter,
        UvBackendAdapter,
    )
    from marimo._environments.environment import Environment
    from marimo._environments.errors import SandboxRestartRequired
    from marimo._environments.sandbox import NotebookSandbox

    source = tmp_path / "notebook.py"
    source.write_text("# /// script\n# dependencies = []\n# ///\n")
    active = Environment(
        python="/active/bin/python", root="/active", action="unchanged"
    )
    moved = Environment(
        python="/other/bin/python", root="/other", action="updated"
    )
    adapter = UvBackendAdapter() if backend == "uv" else PixiBackendAdapter()
    monkeypatch.setattr(adapter, "ensure_available_async", AsyncMock())
    sync = AsyncMock(return_value=active if backend == "uv" else moved)
    target = (
        "marimo._environments.environment.sync_async"
        if backend == "uv"
        else "marimo._environments.pixi.sync_async"
    )
    monkeypatch.setattr(target, sync)
    sandbox = NotebookSandbox(
        str(source), backend, environment=active, adapter=adapter
    )
    if backend == "pixi":
        with pytest.raises(SandboxRestartRequired):
            await sandbox.sync_async()
    else:
        await sandbox.sync_async()
        assert sync.call_args.kwargs["active_environment"] == active
    assert sandbox.environment == active
