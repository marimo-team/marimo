# Test for PollingFileWatcher
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from marimo._utils.file_watcher import FileWatcherManager, PollingFileWatcher


async def test_polling_file_watcher() -> None:
    with NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    callback_calls: list[Path] = []

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


@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="File watcher tests require Python 3.10+",
)
async def test_file_watcher_manager() -> None:
    # Create two temporary files
    with (
        NamedTemporaryFile(delete=False) as tmp_file1,
        NamedTemporaryFile(delete=False) as tmp_file2,
    ):
        tmp_path1 = Path(tmp_file1.name)
        tmp_path2 = Path(tmp_file2.name)

    # Create manager and add callbacks
    manager = FileWatcherManager()

    try:
        # Track callback calls
        callback1_calls: list[Path] = []
        callback2_calls: list[Path] = []
        callback3_calls: list[Path] = []

        async def callback1(path: Path) -> None:
            callback1_calls.append(path)

        async def callback2(path: Path) -> None:
            callback2_calls.append(path)

        async def callback3(path: Path) -> None:
            callback3_calls.append(path)

        # Speed up polling for tests
        PollingFileWatcher.POLL_SECONDS = 0.1

        # Add two callbacks for file1
        manager.add_callback(tmp_path1, callback1)
        manager.add_callback(tmp_path1, callback2)
        # Add one callback for file2
        manager.add_callback(tmp_path2, callback3)

        # Modify file1
        await asyncio.sleep(0.2)
        with open(tmp_path1, "w") as f:  # noqa: ASYNC101 ASYNC230
            f.write("modification1")

        # Wait for callbacks
        await asyncio.sleep(0.2)

        # Both callbacks should be called for file1
        assert len(callback1_calls) == 1
        assert len(callback2_calls) == 1
        assert len(callback3_calls) == 0
        assert callback1_calls[0] == tmp_path1
        assert callback2_calls[0] == tmp_path1

        # Remove one callback from file1
        manager.remove_callback(tmp_path1, callback1)

        # Modify file1 again
        with open(tmp_path1, "w") as f:  # noqa: ASYNC101 ASYNC230
            f.write("modification2")

        # Wait for callbacks
        await asyncio.sleep(0.2)

        # Only callback2 should be called again
        assert len(callback1_calls) == 1  # unchanged
        assert len(callback2_calls) == 2
        assert len(callback3_calls) == 0

        # Modify file2
        with open(tmp_path2, "w") as f:  # noqa: ASYNC101 ASYNC230
            f.write("modification3")

        # Wait for callbacks
        await asyncio.sleep(0.2)

        # callback3 should be called for file2
        assert len(callback1_calls) == 1
        assert len(callback2_calls) == 2
        assert len(callback3_calls) == 1
        assert callback3_calls[0] == tmp_path2

        # Remove all callbacks
        manager.remove_callback(tmp_path1, callback2)
        manager.remove_callback(tmp_path2, callback3)

        # Modify both files
        with open(tmp_path1, "w") as f:  # noqa: ASYNC101 ASYNC230
            f.write("modification4")
        with open(tmp_path2, "w") as f:  # noqa: ASYNC101 ASYNC230
            f.write("modification4")

        # Wait for potential callbacks
        await asyncio.sleep(0.2)

        # No new calls should happen
        assert len(callback1_calls) == 1
        assert len(callback2_calls) == 2
        assert len(callback3_calls) == 1

    finally:
        # Cleanup
        manager.stop_all()
        os.remove(tmp_path1)
        os.remove(tmp_path2)
