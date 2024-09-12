# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._config.config import (
    merge_default_config,
)
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
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

    # Remove marimo
    k._maybe_register_cell("0", "import os")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' not in contents
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

    # Remove marimo
    k._delete_cell("0")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' not in contents
        assert '"markdown==' in contents
        assert '"os",' not in contents

    # Remove markdown
    k._delete_cell("1")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' not in contents
        assert '"markdown==' not in contents
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
