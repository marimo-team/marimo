# Copyright 2026 Marimo. All rights reserved.
"""Compare uncached, cold-cache, and warm-cache directory listings.

Run: uv run python scripts/benchmarks/file_browser.py
Cold refers to the detector cache, not the operating system's filesystem cache.
The clock is fixed to measure repeated listings within one cache expiry window.
The 10,000-Python-file case intentionally exceeds the 4,096-entry detector cache;
its repeated scans measure eviction pressure, not a fully resident warm cache.
"""

from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from marimo._server.files.os_file_system import (
    OSFileSystem,
    _is_marimo_file_cached,
)


def measure(
    fs: OSFileSystem, directory: Path, *, clear: bool = False
) -> float:
    samples = []
    for _ in range(5):
        if clear:
            _is_marimo_file_cached.cache_clear()
        start = time.perf_counter()
        fs.list_files(str(directory))
        samples.append(time.perf_counter() - start)
    return statistics.median(samples) * 1000


def main() -> None:
    print("files  Python%  uncached_ms  cold_ms  repeat_ms  cache_fit")
    for count, python_every in [(1000, 4), (10000, 4), (10000, 1)]:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for index in range(count):
                suffix = ".py" if index % python_every == 0 else ".txt"
                content = "print('hello')\n"
                if index % (python_every * 2) == 0:
                    content = "import marimo\napp = marimo.App()\n"
                (directory / f"file_{index:05d}{suffix}").write_text(content)
            fs = OSFileSystem()
            with patch(
                "marimo._server.files.os_file_system.time.monotonic",
                return_value=0,
            ):
                with patch(
                    "marimo._server.files.os_file_system._is_marimo_file_cached",
                    _is_marimo_file_cached.__wrapped__,
                ):
                    uncached = measure(fs, directory)
                cold = measure(fs, directory, clear=True)
                warm = measure(fs, directory)
            print(
                f"{count:5d}  {100 // python_every:7d}  {uncached:11.2f}  {cold:7.2f}  {warm:9.2f}  {count // python_every <= 4096}"
            )
    _is_marimo_file_cached.cache_clear()


if __name__ == "__main__":
    main()
