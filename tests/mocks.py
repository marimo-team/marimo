from __future__ import annotations

import difflib
import os
from typing import Callable

from marimo._utils.paths import maybe_make_dirs


def snapshotter(current_file: str) -> Callable[[str, str], None]:
    """
    Utility function to create and compare snapshots.

    If the snapshot doesn't exist, it will be created.

    If the snapshot exists, it will be compared with the new result.
    If the result is different, the test will fail,
    but the snapshot will be updated with the new result.
    """

    def snapshot(filename: str, result: str) -> None:
        filepath = os.path.join(
            os.path.dirname(current_file), "snapshots", filename
        )

        # If snapshot directory doesn't exist, create it
        maybe_make_dirs(filepath)

        def normalize(string: str) -> str:
            return string.replace("\r\n", "\n")

        result = normalize(result)

        # If doesn't exist, create snapshot
        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                f.write(result)
            print("Snapshot updated")

        # Read snapshot
        with open(filepath, "r") as f:
            expected = normalize(f.read())

        assert result, "Result is empty"
        assert expected, "Expected is empty"

        def write_result() -> None:
            with open(filepath, "w") as f:
                f.write(result)

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

            if text_diff:
                write_result()
                print("Snapshot updated")

            assert result == expected, f"Snapshot differs:\n{text_diff}"

    return snapshot
