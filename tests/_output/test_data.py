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


def test_sanitize_json_bigint() -> None:
    # Test with string input
    json_str = '{"bigint": 9007199254740992}'
    assert (
        mo_data.sanitize_json_bigint(json_str)
        == '{"bigint":"9007199254740992"}'
    )

    # Test with dict input
    data_dict = {"bigint": 9007199254740992}
    assert (
        mo_data.sanitize_json_bigint(data_dict)
        == '{"bigint":"9007199254740992"}'
    )

    # Test with list of dicts input
    data_list = [{"bigint": 9007199254740992}]
    assert (
        mo_data.sanitize_json_bigint(data_list)
        == '[{"bigint":"9007199254740992"}]'
    )

    # Test with regular numbers (should not be converted)
    data_dict = {"regular": 42}
    assert mo_data.sanitize_json_bigint(data_dict) == '{"regular":42}'

    # Test with nested structures
    data_dict = {
        "bigint": 9007199254740992,
        "nested": {"bigint": 9007199254740993, "regular": 42},
    }
    assert (
        mo_data.sanitize_json_bigint(data_dict)
        == '{"bigint":"9007199254740992","nested":{"bigint":"9007199254740993","regular":42}}'  # noqa: E501
    )
