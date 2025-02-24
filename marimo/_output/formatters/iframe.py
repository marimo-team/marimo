# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from html.parser import HTMLParser


def maybe_wrap_in_iframe(html_content: str) -> str:
    if _has_script_tag_without_src(html_content):
        from marimo._output.formatting import iframe

        return iframe(html_content).text
    return html_content


def _has_script_tag_without_src(html_content: str) -> bool:
    # Cheap check
    if "<script" not in html_content:
        return False

    parser = ScriptTagParser()
    try:
        parser.feed(html_content)  # type: ignore
        return parser.has_script_without_src
    except StopIteration:
        return parser.has_script_without_src
    except Exception:
        # Don't fail on bad HTML
        return False


class ScriptTagParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.has_script_without_src = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag == "script":
            if not any(attr[0] == "src" for attr in attrs):
                self.has_script_without_src = True
                # Terminate early
                raise StopIteration
