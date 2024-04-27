from __future__ import annotations

import json

import marimo._output.data.data as mo_data


def test_html() -> None:
    html_content = "<html><body><h1>Hello, HTML!</h1></body></html>"
    vfile = mo_data.html(html_content)
    assert vfile.filename.endswith(".html")
    assert (
        vfile.url
        == "data:text/html;base64,PGh0bWw+PGJvZHk+PGgxPkhlbGxvLCBIVE1MITwvaDE+PC9ib2R5PjwvaHRtbD4="  # noqa: E501
    )


def test_text() -> None:
    text_content = "Hello, Text!"
    vfile = mo_data.any_data(text_content, ext="txt")
    assert vfile.filename.endswith(".txt")
    assert vfile.url == "data:text/plain;base64,SGVsbG8sIFRleHQh"


def test_json() -> None:
    json_content = {"key": "value"}
    vfile = mo_data.json(json.dumps(json_content))
    assert vfile.filename.endswith(".json")
    assert vfile.url == "data:application/json;base64,eyJrZXkiOiAidmFsdWUifQ=="


def test_csv() -> None:
    csv_content = "a,b,c\n1,2,3\n4,5,6"
    vfile = mo_data.csv(csv_content)
    assert vfile.filename.endswith(".csv")
    assert vfile.url == "data:text/csv;base64,YSxiLGMKMSwyLDMKNCw1LDY="
