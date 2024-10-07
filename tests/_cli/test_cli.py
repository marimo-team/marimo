# Copyright 2024 Marimo. All rights reserved.
"""
Crude CLI tests

Requires frontend to be built
"""

from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Iterator, Optional

import pytest

from marimo import __version__
from marimo._ast import codegen
from marimo._ast.cell import CellConfig
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.config.config import ROOT_DIR as CONFIG_ROOT_DIR

HAS_UV = DependencyManager.which("uv")

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def _is_win32() -> bool:
    return sys.platform == "win32"


def _can_access_pypi() -> bool:
    try:
        pypi_url = "https://pypi.org/pypi/marimo/json"
        with urllib.request.urlopen(pypi_url, timeout=5):
            return True
    except urllib.error.URLError:
        return False


@contextlib.contextmanager
def _patch_signals_win32() -> Iterator[None]:
    old_handler: Any = None
    try:
        if _is_win32():
            old_handler = signal.signal(signal.SIGINT, lambda *_: ...)
        yield
    finally:
        if old_handler is not None:
            signal.signal(signal.SIGINT, old_handler)


def _interrupt(process: subprocess.Popen) -> None:
    if _is_win32():
        os.kill(process.pid, signal.CTRL_C_EVENT)
    else:
        os.kill(process.pid, signal.SIGINT)


def _confirm_shutdown(process: subprocess.Popen) -> None:
    if _is_win32():
        process.stdin.write(b"y\r\n")
    else:
        process.stdin.write(b"y\n")
    process.stdin.flush()


def _check_shutdown(
    process: subprocess.Popen, check_fn: Optional[Callable[[int], bool]] = None
) -> None:
    max_tries = 3
    tries = 0
    while process.poll() is None and tries < max_tries:
        time.sleep(1)
        tries += 1
    if check_fn is None:
        assert process.poll() == 0
    else:
        assert check_fn(process.poll())


def _try_fetch(
    port: int, host: str = "localhost", token: Optional[str] = None
) -> Optional[bytes]:
    contents = None
    for _ in range(10):
        try:
            url = f"http://{host}:{port}"
            if token is not None:
                url = f"{url}?access_token={token}"
            contents = urllib.request.urlopen(url).read()
            break
        except Exception:
            time.sleep(0.5)
    return contents


def _check_started(port: int, host: str = "localhost") -> Optional[bytes]:
    assert _try_fetch(port, host) is not None


def _temp_run_file(directory: tempfile.TemporaryDirectory) -> str:
    filecontents = codegen.generate_filecontents(
        ["import marimo as mo"], ["one"], cell_configs=[CellConfig()]
    )
    path = os.path.join(directory.name, "run.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(filecontents)
    return path


def _check_contents(
    p: subprocess.Popen,  # type: ignore
    phrase: bytes,
    contents: Optional[bytes],
) -> None:
    try:
        assert contents is not None
        assert phrase in contents
    finally:
        p.kill()


def _get_port() -> int:
    port = 2718
    max_tries = 25
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            in_use = s.connect_ex(("localhost", port)) == 0
        if in_use:
            port += 1
        else:
            return port
    raise OSError("Could not find an unused port.")


def _read_toml(filepath: str) -> Optional[dict]:
    import tomlkit

    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as file:
        return tomlkit.parse(file.read())


def test_cli_help_exit_code() -> None:
    # smoke test: makes sure CLI starts
    # helpful for catching issues related to
    # Python 3.8 compatibility, such as forgetting `from __future__` import
    # annotations
    p = subprocess.run(["marimo", "--help"])
    assert p.returncode == 0


def test_cli_edit_none() -> None:
    # smoke test: makes sure CLI starts and has basic things we expect
    # helpful for catching issues related to
    # Python 3.8 compatibility, such as forgetting `from __future__` import
    # annotations
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "edit",
            "-p",
            str(port),
            "--headless",
            "--no-token",
            "--skip-update-check",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='home'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )
    _check_contents(p, b"marimo-server-token", contents)


def test_cli_edit_token() -> None:
    # smoke test: makes sure CLI starts and has basic things we expect
    # helpful for catching issues related to
    # Python 3.8 compatibility, such as forgetting `from __future__` import
    # annotations
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "edit",
            "-p",
            str(port),
            "--headless",
            "--token-password",
            "secret",
            "--skip-update-check",
        ]
    )
    contents = _try_fetch(port, "localhost", "secret")
    _check_contents(p, b"marimo-mode data-mode='home'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )
    _check_contents(p, b"marimo-server-token", contents)


def test_cli_edit_directory() -> None:
    d = tempfile.TemporaryDirectory()
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "edit",
            d.name,
            "-p",
            str(port),
            "--headless",
            "--no-token",
            "--skip-update-check",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='home'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )
    _check_contents(p, b"marimo-server-token", contents)


def test_cli_edit_new_file() -> None:
    d = tempfile.TemporaryDirectory()
    path = os.path.join(d.name, "new.py")
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "edit",
            path,
            "-p",
            str(port),
            "--headless",
            "--no-token",
            "--skip-update-check",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )
    _check_contents(p, b"marimo-server-token", contents)


def test_cli_edit_with_additional_args(temp_marimo_file: str) -> None:
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "edit",
            temp_marimo_file,
            "-p",
            str(port),
            "--headless",
            "--no-token",
            "--skip-update-check",
            "--",
            "-a=foo",
            "--b=bar",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )


@pytest.mark.skipif(
    condition=not _can_access_pypi(),
    reason="update check won't work without access to pypi",
)
def test_cli_edit_update_check() -> None:
    with tempfile.TemporaryDirectory() as tempdir:
        port = _get_port()
        env = {**os.environ, "MARIMO_PYTEST_HOME_DIR": tempdir}
        # pop off MARIMO_SKIP_UPDATE_CHECK
        env.pop("MARIMO_SKIP_UPDATE_CHECK", None)
        p = subprocess.Popen(
            ["marimo", "edit", "-p", str(port), "--headless", "--no-token"],
            env=env,
        )
        contents = _try_fetch(port)
        _check_contents(p, b"marimo-mode data-mode='home'", contents)

        state_contents = _read_toml(
            os.path.join(tempdir, CONFIG_ROOT_DIR, "state.toml")
        )
        assert state_contents is not None
        assert state_contents.get("last_checked_at") is not None


@pytest.mark.skipif(
    condition=not _can_access_pypi(),
    reason="update check skip is only detectable if pypi is accessible",
)
def test_cli_edit_skip_update_check() -> None:
    with tempfile.TemporaryDirectory() as tempdir:
        port = _get_port()
        p = subprocess.Popen(
            [
                "marimo",
                "edit",
                "-p",
                str(port),
                "--headless",
                "--no-token",
                "--skip-update-check",
            ],
            env={**os.environ, "MARIMO_PYTEST_HOME_DIR": tempdir},
        )
        contents = _try_fetch(port)
        _check_contents(p, b"marimo-mode data-mode='home'", contents)

        state_contents = _read_toml(
            os.path.join(tempdir, CONFIG_ROOT_DIR, "state.toml")
        )
        assert (
            state_contents is None
            or state_contents.get("last_checked_at") is None
        )


def test_cli_new() -> None:
    port = _get_port()
    p = subprocess.Popen(
        ["marimo", "new", "-p", str(port), "--headless", "--no-token"]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )
    _check_contents(p, b"marimo-server-token", contents)


def test_cli_run(temp_marimo_file: str) -> None:
    port = _get_port()
    p = subprocess.Popen(
        ["marimo", "run", temp_marimo_file, "-p", str(port), "--headless"]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='read'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )


def test_cli_run_with_show_code(temp_marimo_file: str) -> None:
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "run",
            temp_marimo_file,
            "-p",
            str(port),
            "--headless",
            "--include-code",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='read'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )


def test_cli_run_with_additional_args(temp_marimo_file: str) -> None:
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "run",
            temp_marimo_file,
            "-p",
            str(port),
            "--headless",
            "--",
            "-a=foo",
            "--b=bar",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='read'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )


def test_cli_tutorial() -> None:
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "tutorial",
            "intro",
            "-p",
            str(port),
            "--headless",
            "--no-token",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )
    _check_contents(p, b"intro.py", contents)


def test_cli_md_tutorial() -> None:
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "tutorial",
            "markdown-format",
            "-p",
            str(port),
            "--headless",
            "--no-token",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )
    _check_contents(p, b"markdown-format.md", contents)


def test_cli_md_run(temp_md_marimo_file: str) -> None:
    port = _get_port()
    p = subprocess.Popen(
        ["marimo", "run", temp_md_marimo_file, "-p", str(port), "--headless"]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='read'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )


def test_cli_md_edit(temp_md_marimo_file: str) -> None:
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "edit",
            temp_md_marimo_file,
            "-p",
            str(port),
            "--no-token",
            "--headless",
            "--skip-update-check",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )


def test_cli_custom_host() -> None:
    port = _get_port()
    host = "localhost"
    p = subprocess.Popen(
        [
            "marimo",
            "tutorial",
            "intro",
            "-p",
            str(port),
            "--headless",
            "--no-token",
            "--host",
            host,
        ]
    )
    contents = _try_fetch(port, host)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)


@pytest.mark.skipif(not HAS_UV, reason="uv is required for sandbox tests")
def test_cli_sandbox_edit(temp_marimo_file: str) -> None:
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "edit",
            temp_marimo_file,
            "-p",
            str(port),
            "--headless",
            "--no-token",
            "--sandbox",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)


@pytest.mark.skipif(not HAS_UV, reason="uv is required for sandbox tests")
def test_cli_sandbox_run(temp_marimo_file: str) -> None:
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "run",
            temp_marimo_file,
            "-p",
            str(port),
            "--headless",
            "--sandbox",
        ]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='read'", contents)


@pytest.mark.xfail(condition=_is_win32(), reason="flaky on Windows")
def test_cli_edit_interrupt_twice() -> None:
    # two SIGINTs should kill the CLI
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "edit",
            "-p",
            str(port),
            "--headless",
            "--no-token",
            "--skip-update-check",
        ]
    )
    _check_started(port)
    with _patch_signals_win32():
        _interrupt(p)
        assert p.poll() is None
        _interrupt(p)
        # exit code is system dependent when killed by signal
        _check_shutdown(p, check_fn=lambda code: code is not None)


@pytest.mark.xfail(condition=_is_win32(), reason="flaky on Windows")
def test_cli_run_interrupt_twice() -> None:
    # two SIGINTs should kill the CLI
    d = tempfile.TemporaryDirectory()
    path = _temp_run_file(d)
    port = _get_port()
    p = subprocess.Popen(
        ["marimo", "run", path, "-p", str(port), "--headless"]
    )
    _check_started(port)
    with _patch_signals_win32():
        _interrupt(p)
        assert p.poll() is None
        _interrupt(p)
        # exit code is system dependent when killed by signal
        _check_shutdown(p, check_fn=lambda code: code is not None)


@pytest.mark.xfail(condition=_is_win32(), reason="flaky on Windows")
def test_cli_edit_shutdown() -> None:
    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "edit",
            "-p",
            str(port),
            "--headless",
            "--no-token",
            "--skip-update-check",
        ],
        stdin=subprocess.PIPE,
    )
    _check_started(port)
    with _patch_signals_win32():
        _interrupt(p)
        assert p.poll() is None

        assert p.stdin is not None
        _confirm_shutdown(p)
        _check_shutdown(p)


@pytest.mark.xfail(condition=_is_win32(), reason="flaky on Windows")
def test_cli_run_shutdown() -> None:
    d = tempfile.TemporaryDirectory()
    path = _temp_run_file(d)
    port = _get_port()
    p = subprocess.Popen(
        ["marimo", "run", path, "-p", str(port), "--headless", "--no-token"],
        stdin=subprocess.PIPE,
    )
    _check_started(port)
    with _patch_signals_win32():
        _interrupt(p)
        assert p.poll() is None
        assert p.stdin is not None
        p.stdin.write(b"y\n")
        p.stdin.flush()
        time.sleep(3)
        assert p.poll() == 0


def test_cli_edit_sandbox_prompt() -> None:
    port = _get_port()
    path = os.path.join(DIR_PATH, "cli_data", "sandbox.py")
    p = subprocess.Popen(
        [
            "marimo",
            "edit",
            path,
            "--headless",
            "--no-token",
            "--skip-update-check",
            "-p",
            str(port),
        ],
        stdin=subprocess.PIPE,
    )
    assert p.poll() is None
    assert p.stdin is not None
    p.stdin.write(b"y\n")
    p.stdin.flush()
    _check_started(port)
    p.kill()


def test_cli_run_sandbox_prompt() -> None:
    port = _get_port()
    path = os.path.join(DIR_PATH, "cli_data", "sandbox.py")
    p = subprocess.Popen(
        [
            "marimo",
            "run",
            path,
            "--headless",
            "--no-token",
            "-p",
            str(port),
        ],
        stdin=subprocess.PIPE,
    )
    assert p.poll() is None
    assert p.stdin is not None
    p.stdin.write(b"y\n")
    p.stdin.flush()
    _check_started(port)
    p.kill()


def test_cli_edit_sandbox_prompt_yes() -> None:
    port = _get_port()
    path = os.path.join(DIR_PATH, "cli_data", "sandbox.py")
    p = subprocess.Popen(
        [
            "marimo",
            "-y",
            "edit",
            path,
            "--headless",
            "--no-token",
            "--skip-update-check",
            "-p",
            str(port),
        ],
    )
    assert p.poll() is None
    _check_started(port)
    p.kill()


def test_cli_run_sandbox_prompt_yes() -> None:
    port = _get_port()
    path = os.path.join(DIR_PATH, "cli_data", "sandbox.py")
    p = subprocess.Popen(
        [
            "marimo",
            "-y",
            "run",
            path,
            "--headless",
            "--no-token",
            "-p",
            str(port),
        ],
    )
    assert p.poll() is None
    _check_started(port)
    p.kill()
