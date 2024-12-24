# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, call, patch

import pytest

from marimo._config.config import (
    merge_default_config,
)
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.requests import InstallMissingPackagesRequest
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
    k._maybe_register_cell("0", "import marimo as mo\nimport os")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' in contents
        assert "markdown" not in contents
        assert '"os",' not in contents

    # Add markdown
    k._maybe_register_cell("1", "import markdown")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' in contents
        assert '"os",' not in contents
        assert '"markdown==' in contents

    # Remove marimo, it's still in requirements
    k._maybe_register_cell("0", "import os")

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
    k._maybe_register_cell("0", "import marimo as mo\nimport os")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' in contents
        assert '"os",' not in contents

    # Add markdown
    k._maybe_register_cell("1", "import markdown")

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
    k._maybe_register_cell("0", "import marimo as mo\nimport os")

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
    k._maybe_register_cell("0", "import marimo as mo\nimport os")

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
    k._maybe_register_cell("0", "import marimo as mo\nimport os")

    with open(filename) as f:  # noqa: ASYNC230
        assert "" == f.read()


async def test_install_missing_packages_micropip(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    # Fake put pyodide in sys.modules
    import sys

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
    import sys

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
    import sys

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
