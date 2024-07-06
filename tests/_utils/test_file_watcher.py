# Test for PollingFileWatcher
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List

from marimo._utils.file_watcher import PollingFileWatcher


async def test_polling_file_watcher() -> None:
    with NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    callback_calls: List[Path] = []

    async def test_callback(path: Path):
        return callback_calls.append(path)

    PollingFileWatcher.POLL_SECONDS = 0.1

    # Create
    loop = asyncio.get_event_loop()
    watcher = PollingFileWatcher(tmp_path, test_callback, loop)
    watcher.start()

    # Wait a bit and then modify the file
    await asyncio.sleep(0.2)
    with open(tmp_path, "w") as f:  # noqa: ASYNC101 ASYNC230
        f.write("modification")

    # Wait for the watcher to detect the change
    await asyncio.sleep(0.2)

    # Stop / cleanup
    watcher.stop()
    os.remove(tmp_path)

    # Assert that the callback was called
    assert len(callback_calls) == 1
    assert callback_calls[0] == tmp_path
