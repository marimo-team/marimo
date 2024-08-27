# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._config.config import (
    merge_default_config,
)
from marimo._dependencies.dependencies import DependencyManager
from tests.conftest import MockedKernel

if TYPE_CHECKING:
    import pathlib

HAS_UV = DependencyManager.which("uv")


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
async def test_add_script_metadata_uv(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
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
                    "add_script_metadata": True,
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
        assert '"markdown",' in contents

    # Remove marimo
    k._maybe_register_cell("0", "import os")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo",' not in contents
        assert '"markdown",' in contents
        assert '"os",' not in contents


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
async def test_add_script_metadata_uv_off(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
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
                    "add_script_metadata": False,
                }
            },
        )
    )

    # Add
    k._maybe_register_cell("0", "import marimo as mo\nimport os")

    with open(filename) as f:  # noqa: ASYNC230
        assert "" == f.read()


async def test_add_script_metadata_pip_noop(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
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
                    "add_script_metadata": True,
                }
            },
        )
    )

    # Add
    k._maybe_register_cell("0", "import marimo as mo\nimport os")

    with open(filename) as f:  # noqa: ASYNC230
        assert "" == f.read()
