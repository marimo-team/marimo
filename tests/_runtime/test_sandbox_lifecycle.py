# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import importlib.metadata
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._environments import script_metadata
from marimo._environments.overlay import RuntimeOverlay
from marimo._environments.sandbox import NotebookSandbox
from marimo._environments.uv import is_uv_available
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.packages.sandbox_package_manager import (
    SandboxPackageManager,
)
from marimo._utils.inline_script_metadata import PyProjectReader
from tests._environments.test_sandbox_interface import FakeBackend
from tests._runtime._helpers.factories import default_app_metadata
from tests._runtime._helpers.session import mocked_kernel_session

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.network
@pytest.mark.skipif(not is_uv_available(), reason="uv is required")
@pytest.mark.parametrize("suffix", [".py", ".md"])
async def test_cell_imports_record_transitive_sandbox_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    notebook = tmp_path / f"notebook{suffix}"
    dependencies = ["marimo", "click>=8"] if suffix == ".py" else ["click>=8"]
    project = {"dependencies": dependencies}
    notebook.write_text(
        script_metadata.dumps(project) + "\n"
        if suffix == ".py"
        else '---\npyproject: |\n  dependencies = ["click>=8"]\n---\n\n# Notebook\n'
    )
    sandbox = NotebookSandbox(str(notebook), "uv")
    plan = sandbox.launch(
        ["-m", "marimo"], overlay=RuntimeOverlay(runtime="marimo")
    )
    assert sandbox.environment is not None
    prefix_version = (
        await asyncio.to_thread(
            subprocess.check_output,
            [
                sandbox.environment.python,
                "-c",
                (
                    "from importlib.metadata import distributions; "
                    "print(next((d.version for d in distributions() "
                    "if d.metadata['Name'] == 'parso'), ''))"
                ),
            ],
            text=True,
        )
    ).strip()
    if suffix == ".md":
        # The Markdown prefix lacks parso; the running kernel's runtime
        # environment still supplies it through marimo's dependencies.
        assert prefix_version == ""
    else:
        assert prefix_version
    installed_version = importlib.metadata.version("parso")
    for key, value in plan.env.items():
        if key.startswith("MARIMO_SANDBOX_"):
            monkeypatch.setenv(key, value)
    monkeypatch.setattr(GLOBAL_SETTINGS, "SANDBOX_MODE", "single")
    monkeypatch.setattr(GLOBAL_SETTINGS, "MANAGE_SCRIPT_METADATA", True)

    with mocked_kernel_session(
        app_metadata=default_app_metadata(filename=str(notebook))
    ) as session:
        session.kernel._maybe_register_cell(
            "0",
            "import parso\nimport os\nimport click\nimport missing_package",
            stale=False,
        )

        assert set(
            PyProjectReader.from_filename(str(notebook)).dependencies
        ) == {
            *dependencies,
            f"parso=={installed_version}",
        }

        # Registering another import must not rewrite the saved requirement.
        before = notebook.read_bytes()
        session.kernel._maybe_register_cell(
            "1", "import parso as other_parso", stale=False
        )
        assert notebook.read_bytes() == before

        # An explicit install owns its requirement; the import callback must
        # not replace that range with an exact pin or redo the install edit.
        manager = session.kernel.packages_callbacks.package_manager
        assert isinstance(manager, SandboxPackageManager)
        assert await manager.install("parso>=0.8", version=None)
        before = notebook.read_bytes()
        assert manager.update_notebook_script_metadata(
            str(notebook),
            packages_to_add=["parso"],
            import_namespaces_to_add=["parso"],
            upgrade=False,
        )
        assert notebook.read_bytes() == before


@pytest.mark.parametrize("operation", ["install", "uninstall"])
async def test_restart_required_batch_saves_every_requirement(
    operation: str,
) -> None:
    from marimo._environments.errors import (
        EnvironmentManagerError,
        SandboxRestartRequired,
    )
    from marimo._environments.sandbox import NotebookSandbox

    sandbox = MagicMock(spec=NotebookSandbox)
    sandbox.backend = "pixi"
    sandbox.environment = None
    mutation = sandbox.add if operation == "install" else sandbox.remove
    mutation.side_effect = SandboxRestartRequired("Restart the kernel")
    manager = SandboxPackageManager(sandbox)

    async def mutate() -> bool:
        if operation == "install":
            return await manager.install("boltons six", version=None)
        return await manager.uninstall("boltons six")

    assert not await mutate()
    assert [call.args[0] for call in mutation.call_args_list] == [
        "boltons",
        "six",
    ]
    assert (manager.restart_required, manager.last_error) == (True, None)

    # A subsequent solver failure is a failure, not another saved-change result.
    mutation.side_effect = EnvironmentManagerError("No solution")
    assert not await mutate()
    assert (manager.restart_required, manager.last_error) == (
        False,
        "No solution",
    )

    mutation.side_effect = None
    assert await mutate()
    assert (manager.restart_required, manager.last_error) == (False, None)


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
