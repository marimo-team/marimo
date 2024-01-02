# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import re

from marimo._output.formatting import as_html
from marimo._output.md import md
from marimo._plugins.core.web_component import (
    build_ui_plugin,
    parse_initial_value,
)


def test_args_escaped() -> None:
    initial_value = "'ello&"
    html = build_ui_plugin(
        "tag-name", initial_value, label=None, args={"text": "a & b"}
    )

    # args should be JSON-encoded and escaped
    match = re.search("data-initial-value='(.*?)'", html)
    assert match is not None
    assert match.groups()[0] == "&quot;&#x27;ello&amp;&quot;"

    match = re.search("data-text='(.*?)'", html)
    assert match is not None
    assert match.groups()[0] == "&quot;a &amp; b&quot;"


def test_initial_value_parse() -> None:
    initial_value = "'ello"
    html = build_ui_plugin("tag-name", initial_value, label=None, args={})

    # extracted value should be unescaped
    assert initial_value == parse_initial_value(html)


def test_label_md_compiled() -> None:
    initial_value = "'ello"
    html = build_ui_plugin("tag-name", initial_value, label="$x$", args={})

    match = re.search("data-label='(.*?)'", html)
    assert match is not None
    # "md"'s latex extension generates spans with class name arithmatex
    assert "arithmatex" in match.groups()[0]


def test_embed_dollar_sign_in_md() -> None:
    markdown = md(as_html(["$", "$"]).text)
    # don't parse dollar in data as latex
    assert "arithmatex" not in markdown.text
