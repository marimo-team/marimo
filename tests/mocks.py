from __future__ import annotations

import difflib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

import pytest

from marimo import __version__
from marimo._utils.paths import maybe_make_dirs


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
                # Old versions of markdown are allowed to have different
                # tags and whitespace
                if sys.version_info < (3, 10):
                    if ToText.apply(result) == ToText.apply(expected):
                        pytest.xfail(
                            "Different tags in older markdown versions"
                        )
                        return

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
