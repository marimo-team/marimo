# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess

COMMAND_TIMEOUT = 10


def error_detail(error: OSError | subprocess.SubprocessError) -> str:
    if isinstance(
        error, (subprocess.CalledProcessError, subprocess.TimeoutExpired)
    ):
        stderr = error.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        if stderr and stderr.strip():
            return stderr.strip()
    return str(error)


def finish_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=COMMAND_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=COMMAND_TIMEOUT)
    if process.stdout is not None:
        process.stdout.close()
