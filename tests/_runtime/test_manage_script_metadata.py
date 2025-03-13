# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pathlib
import sys
from types import ModuleType
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, call, patch

import pytest

from marimo._config.config import merge_default_config
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._dependencies.errors import ManyModulesNotFoundError
from marimo._messaging.ops import InstallingPackageAlert, MissingPackageAlert
from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.pypi_package_manager import (
    MicropipPackageManager,
    PipPackageManager,
)
from marimo._runtime.packages.utils import is_python_isolated
from marimo._runtime.requests import (
    ControlRequest,
    InstallMissingPackagesRequest,
)
from marimo._runtime.runner import cell_runner
from tests.conftest import MockedKernel

if TYPE_CHECKING:
    import pathlib

HAS_UV = DependencyManager.which("uv")


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
async def test_manage_script_metadata_uv(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
    GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = True
    filename = str(tmp_path / "notebook.py")
    # Create empty file
    with open(filename, "w") as f:  # noqa: ASYNC230
        f.write("")

    k = mocked_kernel.k
    await k.rename_file(filename)
    k._update_runtime_from_user_config(
        merge_default_config(
            {
                "package_management": {
                    "manager": "uv",
                }
            },
        )
    )
    # Add marimo, skip os
    k._maybe_register_cell("0", "import marimo as mo\nimport os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' in contents
        assert "markdown" not in contents
        assert '"os",' not in contents

    # Add markdown
    k._maybe_register_cell("1", "import markdown", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' in contents
        assert '"os",' not in contents
        assert '"markdown==' in contents

    # Remove marimo, it's still in requirements
    k._maybe_register_cell("0", "import os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' in contents
        assert '"markdown==' in contents
        assert '"os",' not in contents


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
async def test_manage_script_metadata_uv_deletion(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
    GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = True
    filename = str(tmp_path / "notebook.py")
    # Create empty file
    with open(filename, "w") as f:  # noqa: ASYNC230
        f.write("")

    k = mocked_kernel.k
    await k.rename_file(filename)
    k._update_runtime_from_user_config(
        merge_default_config(
            {
                "package_management": {
                    "manager": "uv",
                }
            },
        )
    )

    # Add marimo, skip os
    k._maybe_register_cell("0", "import marimo as mo\nimport os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' in contents
        assert '"os",' not in contents

    # Add markdown
    k._maybe_register_cell("1", "import markdown", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' in contents
        assert '"os",' not in contents
        assert '"markdown==' in contents

    # Remove marimo, it's still in requirements
    k._delete_cell("0")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' in contents
        assert '"markdown==' in contents
        assert '"os",' not in contents

    # Remove markdown, still in reqs
    k._delete_cell("1")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' in contents
        assert '"markdown==' in contents
        assert '"os",' not in contents


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
async def test_manage_script_metadata_uv_off(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
    GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = False
    filename = str(tmp_path / "notebook.py")
    # Create empty file
    with open(filename, "w") as f:  # noqa: ASYNC230
        f.write("")

    k = mocked_kernel.k
    await k.rename_file(filename)
    k._update_runtime_from_user_config(
        merge_default_config(
            {
                "package_management": {
                    "manager": "uv",
                }
            },
        )
    )

    # Add
    k._maybe_register_cell("0", "import marimo as mo\nimport os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        assert "" == f.read()


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
async def test_manage_script_metadata_uv_no_filename(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
    GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = True
    filename = str(tmp_path / "notebook.py")
    # Create empty file
    with open(filename, "w") as f:  # noqa: ASYNC230
        f.write("")

    k = mocked_kernel.k
    k._update_runtime_from_user_config(
        merge_default_config(
            {
                "package_management": {
                    "manager": "uv",
                }
            },
        )
    )

    # Add
    k._maybe_register_cell("0", "import marimo as mo\nimport os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        assert "" == f.read()


async def test_manage_script_metadata_pip_noop(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
    GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = True
    filename = str(tmp_path / "notebook.py")
    # Create empty file
    with open(filename, "w") as f:  # noqa: ASYNC230
        f.write("")

    k = mocked_kernel.k
    await k.rename_file(filename)
    k._update_runtime_from_user_config(
        merge_default_config(
            {
                "package_management": {
                    "manager": "pip",
                }
            },
        )
    )

    # Add
    k._maybe_register_cell("0", "import marimo as mo\nimport os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        assert "" == f.read()


async def test_install_missing_packages_micropip(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    # Fake put pyodide in sys.modules
    sys.modules["pyodide"] = ModuleType("pyodide")

    with patch("micropip.install", new_callable=AsyncMock) as mock_install:
        await k.install_missing_packages(
            InstallMissingPackagesRequest(
                manager="micropip",
                versions={"barbaz": "", "foobar": ""},
            )
        )
        assert mock_install.call_count == 2
        assert mock_install.call_args_list == [
            call(["barbaz"]),
            call(["foobar"]),
        ]

    # Remove pyodide from sys.modules
    del sys.modules["pyodide"]


async def test_install_missing_packages_micropip_with_versions(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    # Fake put pyodide in sys.modules
    sys.modules["pyodide"] = ModuleType("pyodide")

    with patch("micropip.install", new_callable=AsyncMock) as mock_install:
        await k.install_missing_packages(
            InstallMissingPackagesRequest(
                manager="micropip",
                versions={"numpy": "1.22.0", "pandas": "1.5.0"},
            )
        )
        assert mock_install.call_count == 2
        assert mock_install.call_args_list == [
            call(["numpy==1.22.0"]),
            call(["pandas==1.5.0"]),
        ]

    # Remove pyodide from sys.modules
    del sys.modules["pyodide"]


async def test_install_missing_packages_micropip_other_modules(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k

    k.module_registry.modules = lambda: set(
        {"idk", "done", "already_installed"}
    )
    sys.modules["pyodide"] = ModuleType("pyodide")
    sys.modules["already_installed"] = ModuleType("already_installed")

    with patch("micropip.install", new_callable=AsyncMock) as mock_install:
        await k.install_missing_packages(
            InstallMissingPackagesRequest(
                manager="micropip",
                versions={},
            )
        )
        assert mock_install.call_count == 2
        assert mock_install.call_args_list == [
            call(["done"]),
            call(["idk"]),
        ]

    # Remove pyodide from sys.modules
    del sys.modules["pyodide"]
    del sys.modules["already_installed"]


async def test_broadcast_missing_packages(
    mocked_kernel: MockedKernel,
) -> None:
    """Test that _broadcast_missing_packages correctly handles missing packages for micropip"""
    k = mocked_kernel.k
    control_requests: list[ControlRequest] = []
    broadcast_messages: list[InstallingPackageAlert | MissingPackageAlert] = []

    def mock_enqueue(request: ControlRequest) -> None:
        control_requests.append(request)

    def mock_broadcast(
        msg: InstallingPackageAlert | MissingPackageAlert,
    ) -> None:
        broadcast_messages.append(msg)

    k.enqueue_control_request = mock_enqueue
    InstallingPackageAlert.broadcast = mock_broadcast  # type: ignore
    MissingPackageAlert.broadcast = mock_broadcast  # type: ignore

    sys.modules["pyodide"] = ModuleType("pyodide")

    # Create a mock runner with ModuleNotFoundError
    class MockRunner:
        def __init__(self) -> None:
            self.exceptions = {
                "cell1": ModuleNotFoundError(
                    "No module named 'numpy'", name="numpy"
                ),
                # Duplicate
                "cell2": ModuleNotFoundError(
                    "No module named 'numpy'", name="numpy"
                ),
                # Has mapping
                "ibis": ModuleNotFoundError(
                    "No module named 'ibis'", name="ibis"
                ),
                "cell3": ManyModulesNotFoundError(
                    package_names=["grouped_one", "grouped_two"],
                    msg="Missing one and two",
                ),
            }

    # Case 1: Auto-install enabled
    with patch("micropip.install", new_callable=AsyncMock):
        runner = cast(cell_runner.Runner, MockRunner())
        k.package_manager = create_package_manager("micropip")
        package_manager = k.package_manager
        assert isinstance(package_manager, MicropipPackageManager)
        k._broadcast_missing_packages(runner)

        # Should create install request
        assert len(control_requests) == 1
        request = control_requests[0]
        assert isinstance(request, InstallMissingPackagesRequest)
        assert request.manager == package_manager.name
        assert request.versions == {
            "numpy": "",
            "ibis-framework[duckdb]": "",
            "grouped-one": "",
            "grouped-two": "",
        }
        assert len(broadcast_messages) == 0

        # Case 2: Auto-install disabled
        control_requests.clear()
        broadcast_messages.clear()
        package_manager.should_auto_install = lambda: False  # type: ignore
        k._broadcast_missing_packages(runner)

        # Should broadcast alert instead of installing
        assert len(control_requests) == 0
        assert len(broadcast_messages) == 1
        alert = broadcast_messages[0]
        assert isinstance(alert, MissingPackageAlert)
        assert alert.packages == [
            "grouped-one",
            "grouped-two",
            "ibis-framework[duckdb]",
            "numpy",
        ]
        assert alert.isolated == is_python_isolated()

        # Case 3: Multiple missing modules
        control_requests.clear()
        broadcast_messages.clear()
        k.module_registry.missing_modules = lambda: {
            "ibis-framework[duckdb]",
            "pandas",
            "scipy",
        }  # type: ignore
        package_manager.should_auto_install = lambda: True  # type: ignore
        k._broadcast_missing_packages(runner)

        # Should create install request with all missing packages
        assert len(control_requests) == 1
        request = control_requests[0]
        assert isinstance(request, InstallMissingPackagesRequest)
        assert request.manager == package_manager.name
        assert request.versions == {
            "grouped-one": "",
            "grouped-two": "",
            "ibis-framework[duckdb]": "",
            "numpy": "",
            "pandas": "",
            "scipy": "",
        }

        # Case 4: Already attempted packages should be filtered
        control_requests.clear()
        broadcast_messages.clear()
        package_manager.attempted_to_install = (
            lambda package: package == "numpy"
        )  # type: ignore
        k._broadcast_missing_packages(runner)

        # Should only include packages not yet attempted
        assert len(control_requests) == 1
        request = control_requests[0]
        assert isinstance(request, InstallMissingPackagesRequest)
        assert request.manager == package_manager.name
        assert request.versions == {
            "grouped-one": "",
            "grouped-two": "",
            "ibis-framework[duckdb]": "",
            "pandas": "",
            "scipy": "",
        }

    del sys.modules["pyodide"]


def test_broadcast_missing_packages_pip(
    mocked_kernel: MockedKernel,
) -> None:
    """Test that _broadcast_missing_packages correctly handles missing packages for pip"""
    k = mocked_kernel.k
    control_requests: list[ControlRequest] = []
    broadcast_messages: list[InstallingPackageAlert | MissingPackageAlert] = []

    def mock_enqueue(request: ControlRequest) -> None:
        control_requests.append(request)

    def mock_broadcast(
        msg: InstallingPackageAlert | MissingPackageAlert,
    ) -> None:
        broadcast_messages.append(msg)

    k.enqueue_control_request = mock_enqueue
    InstallingPackageAlert.broadcast = mock_broadcast  # type: ignore
    MissingPackageAlert.broadcast = mock_broadcast  # type: ignore

    # Create a mock runner with ModuleNotFoundError
    class MockRunner:
        def __init__(self) -> None:
            self.exceptions = {
                "cell1": ModuleNotFoundError(
                    "No module named 'numpy'", name="numpy"
                ),
                # Duplicate
                "cell2": ModuleNotFoundError(
                    "No module named 'numpy'", name="numpy"
                ),
                # Has mapping
                "ibis": ModuleNotFoundError(
                    "No module named 'ibis'", name="ibis"
                ),
            }

    k.package_manager = create_package_manager("pip")
    package_manager = k.package_manager
    assert isinstance(package_manager, PipPackageManager)
    package_manager.install = AsyncMock()
    runner = cast(cell_runner.Runner, MockRunner())

    # Case 1: Missing modules with auto-install disabled
    k.module_registry.missing_modules = lambda: {"numpy", "pandas"}  # type: ignore
    package_manager.should_auto_install = lambda: False  # type: ignore
    k._broadcast_missing_packages(runner)

    # Should broadcast alert instead of installing
    assert len(control_requests) == 0
    assert len(broadcast_messages) == 1
    alert = broadcast_messages[0]
    assert isinstance(alert, MissingPackageAlert)
    assert alert.packages == ["ibis-framework[duckdb]", "numpy", "pandas"]
    assert alert.isolated == is_python_isolated()

    # Case 2: Multiple missing modules with auto-install enabled
    control_requests.clear()
    broadcast_messages.clear()
    k.module_registry.missing_modules = lambda: {
        "ibis-framework[duckdb]",
        "numpy",
        "pandas",
        "scipy",
    }  # type: ignore
    package_manager.should_auto_install = lambda: True  # type: ignore
    k._broadcast_missing_packages(runner)

    # Should create install request with all missing packages
    assert len(control_requests) == 1
    request = control_requests[0]
    assert isinstance(request, InstallMissingPackagesRequest)
    assert request.manager == "pip"
    assert request.versions == {
        "ibis-framework[duckdb]": "",
        "numpy": "",
        "pandas": "",
        "scipy": "",
    }
