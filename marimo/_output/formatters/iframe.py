# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from html.parser import HTMLParser


def maybe_wrap_in_iframe(html_content: str) -> str:
    """Wrap HTML content in an iframe if it contains inline script tags."""
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
    """HTML parser that detects script tags without a src attribute."""

    def __init__(self) -> None:
        super().__init__()
        self.has_script_without_src = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """Set has_script_without_src=True and stop early on first inline script tag."""
        if tag == "script":
            if not any(attr[0] == "src" for attr in attrs):
                self.has_script_without_src = True
                # Terminate early
                raise StopIteration
