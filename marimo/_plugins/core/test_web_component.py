# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import re

from marimo._output.formatting import as_html
from marimo._output.md import md
from marimo._plugins.core.web_component import (
    build_ui_plugin,
)


def test_args_escaped() -> None:
    initial_value = "'ello&"
    html, data = build_ui_plugin(
        "tag-name", initial_value, label=None, args={"text": "a & b"}
    )

    # args should be JSON-encoded and escaped
    match = re.search("data-initial-value='(.*?)'", html)
    assert match is not None
    locator_id = match.groups()[0]
    assert data[locator_id] == initial_value

    match = re.search("data-text='(.*?)'", html)
    assert match is not None
    locator_id = match.groups()[0]
    assert data[locator_id] == "a & b"


def test_label_md_compiled() -> None:
    initial_value = "'ello"
    html, data = build_ui_plugin(
        "tag-name", initial_value, label="$x$", args={}
    )

    match = re.search("data-label='(.*?)'", html)
    assert match is not None
    # "md"'s latex extension generates spans with class name arithmatex
    locator_id = match.groups()[0]
    assert "arithmatex" in data[locator_id]


def test_embed_dollar_sign_in_md() -> None:
    markdown = md(as_html(["$", "$"]).text)
    # don't parse dollar in data as latex
    assert "arithmatex" not in markdown.text
