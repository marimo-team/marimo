# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import subprocess


def test_config_show() -> None:
    p = subprocess.run(
        ["marimo", "config", "show"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
    output = p.stdout.decode()
    assert "User config from" in output
    assert "[formatting]" in output


def test_config_describe() -> None:
    p = subprocess.run(
        ["marimo", "config", "describe"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
