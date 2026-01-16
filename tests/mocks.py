from __future__ import annotations

import difflib
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol

import pytest

from marimo import __version__
from marimo._utils.paths import maybe_make_dirs
from marimo._utils.platform import is_windows


class SnapshotFunc(Protocol):
    def __call__(
        self, filename: str, result: str, keep_version: bool = False
    ) -> None: ...


class ToText(HTMLParser):
    def __init__(self) -> None:
        HTMLParser.__init__(self)
        self._text = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if len(text) > 0:
            text = re.sub("[ \t\r\n]+", " ", text)
            self._text.append(text.strip())

    def text(self) -> str:
        return " ".join(self._text).strip()

    @staticmethod
    def apply(html: str) -> str:
        parser = ToText()
        parser.feed(html)
        parser.close()
        return parser.text()


def snapshotter(current_file: str) -> SnapshotFunc:
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


def delete_lines_with_files(output: str) -> str:
    """Remove file paths from error messages for consistent snapshots."""

    def remove_file_name(line: str) -> str:
        if "File " not in line:
            return line
        start = line.index("File ")
        if ".py" in line[start:]:
            end = line.rindex(".py") + 3
            return line[0:start] + line[end:]
        return line

    return "\n".join(remove_file_name(line) for line in output.splitlines())


def simplify_images(output: str) -> str:
    """Simplify image paths for consistent snapshots."""
    # Handle data URLs
    output = re.sub(
        r"data:image/png;base64,.*",
        "data:image/png;base64,IMAGE_BASE64_DATA",
        output,
    )

    # Handle "image/png": "*"
    output = re.sub(
        r'"image/png": ".*"',
        '"image/png": "IMAGE_BASE64_DATA"',
        output,
    )
    return output


NON_WINDOWS_EDGE_CASE_FILENAMES = [
    "test<script>.py",
    'test"quotes".py',
]


EDGE_CASE_FILENAMES = [
    # Unicode characters
    "tést.py",
    "café.py",
    "测试.py",
    "🚀notebook.py",
    # Spaces
    "test file with spaces.py",
    # Mixed unicode and spaces
    "café notebook.py",
    "测试 file.py",
    # Injection attempts
    *(NON_WINDOWS_EDGE_CASE_FILENAMES if not is_windows() else []),
]
