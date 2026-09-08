# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.packages.sandbox_package_manager import (
    SandboxPackageManager,
)
from tests._environments.test_sandbox_interface import FakeBackend
from tests._runtime._helpers.factories import default_app_metadata
from tests._runtime._helpers.session import mocked_kernel_session

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


async def test_rename_rebinds_packages_before_rerunning_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._environments import backends

    original = tmp_path / "original.py"
    renamed = tmp_path / "renamed.py"
    original.write_text("# /// script\n# dependencies = []\n# ///\n")
    adapter = FakeBackend(tmp_path / "environment")
    monkeypatch.setattr(backends, "adapter_for", lambda *_args: adapter)
    monkeypatch.setattr(GLOBAL_SETTINGS, "SANDBOX_MODE", "multi")
    with mocked_kernel_session(
        app_metadata=default_app_metadata(filename=str(original)),
        reactive_mode="autorun",
    ) as session:
        kernel = session.kernel
        manager = kernel.packages_callbacks.package_manager
        assert isinstance(manager, SandboxPackageManager)
        # A cell dependent on __file__ can request packages during rename.
        kernel.globals["install"] = lambda: manager._sandbox.add("obstore")
        await kernel.run(
            [
                ExecuteCellCommand(
                    cell_id="0", code="path = __file__; install()"
                )
            ]
        )
        assert not kernel.errors
        original.rename(renamed)

        await kernel.rename_file(str(renamed))

        assert not kernel.errors
        assert adapter.sync_targets[-1] == str(renamed)
        assert not original.exists()
        assert "obstore" in renamed.read_text()


async def test_unnamed_sandbox_keeps_manifest_and_manager_on_save(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._environments import backends
    from marimo._environments.overlay import RuntimeOverlay
    from marimo._environments.sandbox import NotebookSandbox

    adapter = FakeBackend(tmp_path / "environment")
    monkeypatch.setattr(backends, "adapter_for", lambda *_args: adapter)
    outer = NotebookSandbox(None, "uv")
    plan = outer.launch(
        ["-m", "marimo"], overlay=RuntimeOverlay(runtime="marimo")
    )
    for key, value in plan.env.items():
        if key.startswith("MARIMO_SANDBOX_"):
            monkeypatch.setenv(key, value)
    monkeypatch.setattr(GLOBAL_SETTINGS, "SANDBOX_MODE", "single")
    try:
        with mocked_kernel_session(
            app_metadata=default_app_metadata(filename=None)
        ) as session:
            kernel = session.kernel
            manager = kernel.packages_callbacks.package_manager
            assert isinstance(manager, SandboxPackageManager)
            assert await manager.install("obstore", version=None)
            saved = tmp_path / "saved.py"
            saved.write_text("import marimo\n")

            # MULTI's session owns and releases the temporary manifest;
            # the kernel must follow the binding without copying it again.
            outer.rebind(str(saved))

            await kernel.rename_file(str(saved))
            kernel.packages_callbacks.update_package_manager("pip")

            assert kernel.packages_callbacks.package_manager is manager
            assert "obstore==0.8.2" in saved.read_text()
            assert "requires-python" in saved.read_text()
            assert await manager.uninstall("obstore")
            assert "obstore" not in saved.read_text()
            assert adapter.sync_targets[-1] == str(saved)
    finally:
        outer.close()
