from __future__ import annotations

import difflib
from pathlib import Path
from typing import Callable

import pytest

from marimo import __version__
from marimo._utils.paths import maybe_make_dirs


def snapshotter(current_file: str) -> Callable[[str, str], None]:
    """
    Utility function to create and compare snapshots.

    If the snapshot doesn't exist, it will be created.

    If the snapshot exists, it will be compared with the new result.
    If the result is different, the test will fail,
    but the snapshot will be updated with the new result.
    """

    def snapshot(
        filename: str, result: str, keep_version: bool = False
    ) -> None:
        filepath = Path(current_file).parent / "snapshots" / filename

        if not keep_version:
            result = _sanitize_version(result)

        # If snapshot directory doesn't exist, create it
        maybe_make_dirs(filepath)

        def normalize(string: str) -> str:
            return string.replace("\r\n", "\n")

        result = normalize(result)

        # If doesn't exist, create snapshot
        if not filepath.exists():
            filepath.write_text(result)
            print("Snapshot updated")
            return

        # Read snapshot
        expected = normalize(filepath.read_text())

        assert result, "Result is empty"
        assert expected, "Expected is empty"

        def write_result() -> None:
            filepath.write_text(result)

        is_json = filename.endswith(".json")
        if is_json:
            import json

            expected_json = json.loads(expected)
            result_json = json.loads(result)

            if expected_json != result_json:
                write_result()
                print("Snapshot updated")

            assert expected_json == result_json
        else:
            text_diff = "\n".join(
                list(
                    difflib.unified_diff(
                        expected.splitlines(),
                        result.splitlines(),
                        lineterm="",
                    )
                )
            )

            if result != expected:
                write_result()
                print("Snapshot updated")

                # If the snapshot only differs by whitespace,
                # provide a more helpful error message.
                if result.strip() == expected.strip():
                    print("Snapshot only differs by whitespace (.strip())")

                pytest.fail(f"Snapshot differs: '{text_diff}'")

    return snapshot


def _sanitize_version(output: str) -> str:
    return output.replace(f"{__version__} (editable)", "0.0.0").replace(
        f"{__version__}", "0.0.0"
    )
