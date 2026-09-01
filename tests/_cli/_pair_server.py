# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

import websockets.sync.client

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from websockets.sync.client import ClientConnection


@dataclass(frozen=True)
class PairTestServer:
    url: str
    session_id: str
    _process: subprocess.Popen[bytes]
    _websocket: ClientConnection

    def wait_for_kernel(
        self,
        state: str,
        *,
        timeout: float = 10.0,
    ) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            request = urllib.request.Request(
                f"{self.url}/api/kernel/status",
                headers={"Marimo-Session-Id": self.session_id},
            )
            try:
                with urllib.request.urlopen(request, timeout=1) as response:
                    current = json.load(response)["state"]
                if current == state:
                    return
            except (OSError, KeyError, ValueError):
                pass
            time.sleep(0.05)
        raise TimeoutError(
            f"kernel did not become {state!r} within {timeout}s"
        )

    def close(self) -> None:
        try:
            request = urllib.request.Request(
                f"{self.url}/api/kernel/restart_session",
                method="POST",
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "Marimo-Session-Id": self.session_id,
                },
            )
            with urllib.request.urlopen(request, timeout=5):
                pass
        except OSError:
            pass
        try:
            self._websocket.close()
        except OSError:
            pass
        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def _tail(path: Path) -> str:
    try:
        return path.read_text(errors="replace")[-4000:]
    except OSError:
        return ""


def _wait_for_server(
    url: str,
    process: subprocess.Popen[bytes],
    stderr_path: Path,
    *,
    timeout: float = 15.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"marimo server exited with code {process.returncode}:\n"
                f"{_tail(stderr_path)}"
            )
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(
        f"marimo server at {url} did not start in {timeout}s:\n"
        f"{_tail(stderr_path)}"
    )


def _wait_for_kernel_ready(
    websocket: ClientConnection,
    *,
    timeout: float = 10.0,
) -> None:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("kernel did not become ready")
        message = json.loads(websocket.recv(timeout=remaining))
        if message.get("op") == "kernel-ready":
            return


@contextmanager
def pair_test_server(tmp_path: Path) -> Generator[PairTestServer, None, None]:
    port = _free_port()
    notebook = tmp_path / "pair-integration.py"
    notebook.write_text("import marimo\napp = marimo.App()\n")
    stderr_path = tmp_path / "marimo-stderr.log"

    with stderr_path.open("wb") as stderr_file:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "marimo",
                "edit",
                str(notebook),
                "--headless",
                "--no-token",
                "--no-skew-protection",
                "--port",
                str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
        )
        url = f"http://127.0.0.1:{port}"
        try:
            _wait_for_server(url, process, stderr_path)
            session_id = f"pair_{uuid.uuid4().hex[:8]}"
            websocket = websockets.sync.client.connect(
                f"ws://127.0.0.1:{port}/ws?session_id={session_id}",
                open_timeout=5,
            )
            _wait_for_kernel_ready(websocket)
            server = PairTestServer(
                url=url,
                session_id=session_id,
                _process=process,
                _websocket=websocket,
            )
            try:
                yield server
            finally:
                server.close()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
