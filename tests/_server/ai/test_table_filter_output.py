# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from marimo._plugins.ui._impl.tables.filter_context import FilterContext
from marimo._server.ai.table_filter import (
    JSON_OUTPUT_INSTRUCTIONS,
    build_table_filter_prompt,
)
from marimo._server.ai.table_filter_output import (
    TEXT_OUTPUT_INSTRUCTIONS,
    TableFilterOutput,
    TableFilterOutputError,
    decode_table_filter_text,
    table_filter_text_prompt,
)


@pytest.mark.parametrize("field", ["fql", "explanation"])
def test_output_preserves_exact_payload(field: str) -> None:
    payload = '  column_0:"/^chev\\d+$/"\nFQL\nEXPLANATION\n"東京"  '
    expected = {"fql": None, "explanation": None, field: payload}
    output = TableFilterOutput.model_validate(expected)
    assert {
        "output": output.model_dump(),
        "text_round_trip": decode_table_filter_text(
            output.as_text()
        ).model_dump(),
        "json_round_trip": TableFilterOutput.model_validate_json(
            output.model_dump_json()
        ).model_dump(),
    } == {
        "output": expected,
        "text_round_trip": expected,
        "json_round_trip": expected,
    }


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"fql": "column_0=4"},
        {"explanation": "No column"},
        {"fql": None, "explanation": None},
        {"fql": "column_0=4", "explanation": "No column"},
        {"fql": "column_0=4", "explanation": ""},
        {"fql": "", "explanation": "No column"},
        {"fql": "", "explanation": None},
        {"fql": " \n\t", "explanation": None},
        {"fql": None, "explanation": " \n\t"},
        {"fql": 4, "explanation": None},
        {"fql": None, "explanation": False},
        {"fql": ["column_0=4"], "explanation": None},
        {"fql": "column_0=4", "explanation": None, "aliases": []},
    ],
)
def test_output_rejects_invalid_envelopes(value: object) -> None:
    with pytest.raises(ValidationError):
        TableFilterOutput.model_validate(value)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "FQL\n  column_0=4\n  ",
            {"fql": "  column_0=4\n  ", "explanation": None},
        ),
        (
            "EXPLANATION\nNo column.\nFQL\nEXPLANATION\n",
            {"fql": None, "explanation": "No column.\nFQL\nEXPLANATION\n"},
        ),
        (
            "FQL\r\ncolumn_0=4\r\n",
            {"fql": "column_0=4\r\n", "explanation": None},
        ),
        (
            'FQL\n{"fql":"column_0=4","explanation":null}',
            {
                "fql": '{"fql":"column_0=4","explanation":null}',
                "explanation": None,
            },
        ),
    ],
)
def test_text_decoder_uses_only_first_line(
    text: str, expected: dict[str, str | None]
) -> None:
    assert decode_table_filter_text(text).model_dump() == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "FQL",
        "EXPLANATION",
        "column_0=4",
        ' {"fql":"column_0=4","explanation":null}',
        "```\nFQL\ncolumn_0=4\n```",
        "\nFQL\ncolumn_0=4",
        " FQL\ncolumn_0=4",
        "FQL \ncolumn_0=4",
        "fql\ncolumn_0=4",
        "FQL: column_0=4\n",
        "FQL\n",
        "EXPLANATION\n",
        "FQL\n \r\n\t",
        "EXPLANATION\n \r\n\t",
    ],
)
def test_text_decoder_rejects_missing_markers_and_empty_payloads(
    text: str,
) -> None:
    with pytest.raises(TableFilterOutputError, match="table-filter response"):
        decode_table_filter_text(text)


def test_text_prompt_changes_result_format_without_changing_context() -> None:
    prompt = build_table_filter_prompt(
        FilterContext(row_count=None, columns=[], omissions=[]),
        '  Keep "this" request\nunchanged.  ',
    )
    original = deepcopy(prompt)
    text_prompt = table_filter_text_prompt(prompt)
    assistant_outputs = iter(
        [
            'FQL\nvehicle_make:"chev*"',
            'FQL\nactive:true AND (vehicle_make="chevrolet" OR price>1500)',
            "FQL\nvehicle_make:null OR dispatch_time:null",
            "EXPLANATION\nThe table has no horsepower column.",
            (
                "EXPLANATION\nThe median price is unavailable. "
                "Provide a concrete price threshold instead."
            ),
        ]
    )
    assert {
        "system_prompt": text_prompt.system_prompt,
        "messages": text_prompt.messages,
        "aliases": text_prompt.aliases,
        "original": prompt,
    } == {
        "system_prompt": TEXT_OUTPUT_INSTRUCTIONS
        + original.system_prompt.removeprefix(JSON_OUTPUT_INSTRUCTIONS),
        "messages": [
            {
                **message,
                "parts": [{"type": "text", "text": next(assistant_outputs)}],
            }
            if message["role"] == "assistant"
            else message
            for message in original.messages
        ],
        "aliases": original.aliases,
        "original": original,
    }
