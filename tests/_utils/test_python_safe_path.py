# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK = REPO_ROOT / "scripts" / "check_python_safe_path.py"


def run_check(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), *(str(path) for path in paths)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("command", "safe"),
    [
        ('[sys.executable, "-m", "marimo"]', False),
        ('[sys.executable, "-c", code]', False),
        ('[self._python_exe, "-m", "pip"]', False),
        ('[venv_python, "-c", code]', False),
        ("(sys.executable, *args)", False),
        ('["python3.11", "-m", "marimo"]', False),
        ('["/venv/bin/python", "-m", "marimo"]', False),
        ('[*uv, "run", "--", "python", *args]', False),
        ('[sys.executable, "-m", "marimo", "-P"]', False),
        ('[sys.executable, "-c", "print(1)", "-P"]', False),
        ('[sys.executable, "-Wignore::ImportWarning", "-m", "marimo"]', False),
        ('[sys.executable, "-X", "PYTHON", "-m", "marimo"]', False),
        ('[sys.executable, "-P", "-m", "marimo"]', True),
        ('[sys.executable, "-I", "-c", code]', True),
        ('[sys.executable, "-uP", *args]', True),
        ('[sys.executable, "-W", "error", "-P", *args]', True),
        ('[sys.executable, "-Xdev", "-P", *args]', True),
        ('[*uv, "run", "--", "python", "-P", *args]', True),
        ('["-m", "marimo", *args]', True),
        ('["-c", script, payload]', True),
        ('["uv", "pip", "install", "--python", sys.executable]', True),
        ('["node", "-c", script]', True),
        ('("python", "sql", "markdown")', True),
        ('Literal["python", "sql"]', True),
    ],
)
def test_python_command_check(
    tmp_path: Path, command: str, safe: bool
) -> None:
    source = tmp_path / "command.py"
    source.write_text(f"command = {command}\n")
    result = run_check(source)
    assert result.returncode == (0 if safe else 1), result.stderr
    if not safe:
        assert (
            f"{source}:1: Python helper command must include -P"
            in result.stderr
        )


@pytest.mark.parametrize("flag", ["", '"-P", '])
def test_embedded_python_bootstrap(tmp_path: Path, flag: str) -> None:
    source = tmp_path / "bootstrap.py"
    source.write_text(
        'BOOTSTRAP = """\\\n'
        "import os, sys\n"
        f"os.execv(sys.executable, [sys.executable, {flag}*sys.argv[2:]])\n"
        '"""\n'
    )
    result = run_check(tmp_path)
    assert result.returncode == (0 if flag else 1), result.stderr
    if not flag:
        assert f"{source}:1:" in result.stderr


def test_repository_python_commands_use_safe_paths() -> None:
    result = run_check()
    assert result.returncode == 0, result.stderr
