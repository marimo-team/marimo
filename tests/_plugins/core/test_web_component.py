# Copyright 2026 Marimo. All rights reserved.
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


# DOMPurify's SAFE_FOR_XML rule strips any attribute whose value matches
# `]>`, `-->`, `--!>`, or `</(style|script|title|xmp|textarea|noscript|iframe
# |noembed|noframes)`. `_build_attr` must emit JSON-escaped `<`/`>` so the
# parsed attribute value never contains those literals.
SAFE_FOR_XML_TRIGGERS = [
    "]>",
    "]>>",
    "[Cl:31]>>[c:1]",
    "<script>alert(1)</script>",
    "<!-- comment -->",
    "<!--!>",
    "</style>",
    "</textarea>",
    "</iframe>",
]


def _attr_value(html: str, name: str) -> str:
    import html as _html_mod

    match = re.search(f"data-{name}='(.*?)'", html)
    assert match is not None
    return _html_mod.unescape(match.groups()[0])


def test_build_attr_escapes_angle_brackets() -> None:
    for raw in SAFE_FOR_XML_TRIGGERS:
        html = build_ui_plugin(
            "tag-name", initial_value=raw, label=None, args={"data": raw}
        )
        for attr_name in ("initial-value", "data"):
            parsed = _attr_value(html, attr_name)
            assert ">" not in parsed, (raw, attr_name, parsed)
            assert "<" not in parsed, (raw, attr_name, parsed)


def test_initial_value_roundtrip_with_angle_brackets() -> None:
    for raw in SAFE_FOR_XML_TRIGGERS:
        html = build_ui_plugin(
            "tag-name", initial_value=raw, label=None, args={}
        )
        assert parse_initial_value(html) == raw


def test_build_attr_nested_data_escapes_angle_brackets() -> None:
    nested = {"rows": [{"x": raw} for raw in SAFE_FOR_XML_TRIGGERS]}
    html = build_ui_plugin(
        "tag-name", initial_value=None, label=None, args={"data": nested}
    )
    parsed = _attr_value(html, "data")
    assert ">" not in parsed
    assert "<" not in parsed
