# Copyright 2024 Marimo. All rights reserved.
"""
Crude CLI tests

Requires frontend to be built
"""
import contextlib
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Any, Callable, Iterator, Optional

import pytest

from marimo import __version__
from marimo._ast import codegen
from marimo._ast.cell import CellConfig


def _is_win32() -> bool:
    return sys.platform == "win32"


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
    process, check_fn: Optional[Callable[[int], bool]] = None
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


def _try_fetch(port: int, host: str = "localhost") -> Optional[bytes]:
    contents = None
    for _ in range(10):
        try:
            contents = urllib.request.urlopen(f"http://{host}:{port}").read()
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


def test_cli_help_exit_code() -> None:
    # smoke test: makes sure CLI starts
    # helpful for catching issues related to
    # Python 3.8 compatibility, such as forgetting `from __future__` import
    # annotations
    p = subprocess.run(["marimo", "--help"])
    assert p.returncode == 0


def test_cli_edit() -> None:
    # smoke test: makes sure CLI starts and has basic things we expect
    # helpful for catching issues related to
    # Python 3.8 compatibility, such as forgetting `from __future__` import
    # annotations
    port = _get_port()
    p = subprocess.Popen(["marimo", "edit", "-p", str(port), "--headless"])
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )
    _check_contents(p, b"marimo-server-token", contents)


def test_cli_run() -> None:
    filecontents = codegen.generate_filecontents(
        ["import marimo as mo"], ["one"], cell_configs=[CellConfig()]
    )
    d = tempfile.TemporaryDirectory()
    path = os.path.join(d.name, "run.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(filecontents)

    port = _get_port()
    p = subprocess.Popen(
        ["marimo", "run", path, "-p", str(port), "--headless"]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='read'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )


def test_cli_run_with_show_code() -> None:
    filecontents = codegen.generate_filecontents(
        ["import marimo as mo"], ["one"], cell_configs=[CellConfig()]
    )
    d = tempfile.TemporaryDirectory()
    path = os.path.join(d.name, "run.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(filecontents)

    port = _get_port()
    p = subprocess.Popen(
        [
            "marimo",
            "run",
            path,
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


def test_cli_tutorial() -> None:
    port = _get_port()
    p = subprocess.Popen(
        ["marimo", "tutorial", "intro", "-p", str(port), "--headless"]
    )
    contents = _try_fetch(port)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)
    _check_contents(
        p, f"marimo-version data-version='{__version__}'".encode(), contents
    )
    _check_contents(p, b"intro.py", contents)


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
            "--host",
            host,
        ]
    )
    contents = _try_fetch(port, host)
    _check_contents(p, b"marimo-mode data-mode='edit'", contents)


@pytest.mark.xfail(condition=_is_win32(), reason="flaky on Windows")
def test_cli_edit_interrupt_twice() -> None:
    # two SIGINTs should kill the CLI
    port = _get_port()
    p = subprocess.Popen(["marimo", "edit", "-p", str(port), "--headless"])
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
        ["marimo", "edit", "-p", str(port), "--headless"],
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
        ["marimo", "run", path, "-p", str(port), "--headless"],
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
