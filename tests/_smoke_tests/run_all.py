# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import pathlib
from typing import Any, Dict, Optional

import pytest
import yaml

from marimo._utils.paths import import_files

CONCURRENT_TESTS = 5

config_file = os.path.join(os.path.dirname(__file__), "config.yml")


async def test_all_smoke_tests() -> None:
    root = os.path.realpath(
        str(import_files("marimo").joinpath("_smoke_tests"))
    )
    all_py_paths = list(pathlib.Path(root).rglob("*.py"))
    assert all_py_paths, "No smoke tests found"

    with open(config_file, "r") as f:  # noqa: ASYNC101 ASYNC230
        smoke_test_config = yaml.load(f.read(), Loader=yaml.FullLoader)

    semaphore = asyncio.Semaphore(CONCURRENT_TESTS)
    tasks = [
        _run_test(file, root, smoke_test_config, semaphore)
        for file in all_py_paths
    ]
    await asyncio.gather(*tasks)


async def test_all_examples() -> None:
    root = os.path.realpath(
        str(import_files("marimo").joinpath("../examples"))
    )
    all_py_paths = list(pathlib.Path(root).rglob("*.py"))
    assert all_py_paths, "No examples found"

    with open(config_file, "r") as f:  # noqa: ASYNC101 ASYNC230
        smoke_test_config = yaml.load(f.read(), Loader=yaml.FullLoader)

    semaphore = asyncio.Semaphore(CONCURRENT_TESTS)
    tasks = [
        _run_test(file, root, smoke_test_config, semaphore)
        for file in all_py_paths
    ]
    await asyncio.gather(*tasks)


async def _run_test(
    file: pathlib.Path,
    root: str,
    smoke_test_config: Dict[str, Any],
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        relative_file = str(file.relative_to(root))
        file_config = smoke_test_config.get("files", {}).get(relative_file, {})
        skip = file_config.get("skip", None)
        if skip is True:
            return

        failed_reason: str | list[str] | None = file_config.get(
            "failed_reason", None
        )
        input_data = file_config.get("input", None)

        with open(file, "r") as f:  # noqa: ASYNC101 ASYNC230
            content = f.read()
            if "marimo.App(" not in content:
                return

        process, stdout, stderr = await Cmd(
            f"python {file}", timeout=15, input_data=input_data
        ).run()

        if failed_reason:
            # Expecting an error
            assert (
                process.returncode != 0
            ), f"{relative_file} Expected error: {failed_reason}"
            if isinstance(failed_reason, list):
                assert any(
                    reason in stderr for reason in failed_reason
                ), f"File: {file}. Expected error one of {failed_reason} in {stderr}"  # noqa: E501
            else:
                assert failed_reason in stderr, f"File: {file}"
        # Allow MarimoStop
        elif "MarimoStop" in stderr:
            assert (
                process.returncode != 0
            ), f"{relative_file} Unexpected error: {stderr}"
        else:
            # Expecting no error, allow MarimoStop
            assert (
                process.returncode == 0
            ), f"{relative_file} Unexpected error: {stderr}"
            assert not any(
                line.startswith("Traceback") for line in stderr.splitlines()
            )
            assert not any(
                line.startswith("Traceback") for line in stdout.splitlines()
            )

        print(f"✅ {relative_file}")


class Cmd:
    def __init__(
        self, command: str, timeout: int, input_data: Optional[str] = None
    ):
        self.command = command
        self.timeout = timeout
        self.input_data = input_data

    async def run(self):
        process = await asyncio.create_subprocess_shell(
            self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(
                    input=self.input_data.encode() if self.input_data else None
                ),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            pytest.fail(f"Timeout: {self.command}")

        return process, stdout.decode(), stderr.decode()
