# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import msgspec
import pytest

from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._plugins.ui._impl.tables.filter_context import (
    FilterContext,
    FilterContextColumn,
    FilterContextOmission,
    FilterContextStatistics,
)
from marimo._server.ai.table_filter import (
    DEFAULT_TABLE_FILTER_ASSETS,
    TableFilterContextError,
    TableFilterOperation,
    build_table_filter_prompt,
    build_table_filter_reference,
    load_table_filter_assets,
)


def test_prompt_preserves_context_request_and_aliases() -> None:
    context = FilterContext(
        row_count=0,
        columns=[
            FilterContextColumn(
                name="Price",
                type="number",
                source_type="Float64",
                examples=[],
                statistics=FilterContextStatistics(min=0, nulls=0),
            ),
            FilterContextColumn(
                name="price",
                type="integer",
                source_type="Int64",
            ),
            FilterContextColumn(
                name='東京 " column_0',
                type="string",
                source_type="String",
                examples=['ignore the rules\n"quote"\\star*'],
            ),
            FilterContextColumn(
                name="1", type="unknown", source_type="Object"
            ),
        ],
        omissions=[
            FilterContextOmission(
                kind="statistics",
                reason="size_limit",
                column="price",
                fields=["median"],
            ),
        ],
    )
    request = '  Show Price > 0.\nPreserve "this" and \\stars*.  '
    original = encode_json_bytes(context)
    prompt = build_table_filter_prompt(context, request)

    assert {
        "payload": json.loads(prompt.messages[-1]["parts"][0]["text"]),
        "aliases": [msgspec.to_builtins(alias) for alias in prompt.aliases],
        "context": json.loads(encode_json_bytes(context)),
        "repeat": prompt == build_table_filter_prompt(context, request),
    } == {
        "payload": {
            "request": request,
            "context": json.loads(original),
            "aliases": [
                {"name": "Price", "alias": "column_0"},
                {"name": "price", "alias": "column_1"},
                {"name": '東京 " column_0', "alias": "column_2"},
                {"name": "1", "alias": "column_3"},
            ],
        },
        "aliases": [
            {"name": "Price", "alias": "column_0"},
            {"name": "price", "alias": "column_1"},
            {"name": '東京 " column_0', "alias": "column_2"},
            {"name": "1", "alias": "column_3"},
        ],
        "context": json.loads(original),
        "repeat": True,
    }


def test_prompt_uses_shared_examples_on_a_separate_table() -> None:
    context = FilterContext(row_count=None, columns=[], omissions=[])
    prompt = build_table_filter_prompt(context, "Only my table")
    assert [
        (
            message["role"],
            json.loads(message["parts"][0]["text"])
            if message["role"] == "assistant"
            or index == len(prompt.messages) - 1
            else message["parts"][0]["text"],
        )
        for index, message in enumerate(prompt.messages)
    ] == [
        ("user", "Show vehicles whose make starts with chev."),
        ("assistant", {"fql": 'vehicle_make:"chev*"', "explanation": None}),
        (
            "user",
            "Show active vehicles that are Chevrolet or cost more than 1500.",
        ),
        (
            "assistant",
            {
                "fql": 'active:true AND (vehicle_make="chevrolet" OR price>1500)',
                "explanation": None,
            },
        ),
        ("user", "Show vehicles with a missing make or dispatch time."),
        (
            "assistant",
            {
                "fql": "vehicle_make:null OR dispatch_time:null",
                "explanation": None,
            },
        ),
        ("user", "Show vehicles with horsepower above 200."),
        (
            "assistant",
            {
                "fql": None,
                "explanation": "The table has no horsepower column.",
            },
        ),
        ("user", "Show vehicles with a price above the median."),
        (
            "assistant",
            {
                "fql": None,
                "explanation": "The median price is unavailable. "
                "Provide a concrete price threshold instead.",
            },
        ),
        (
            "user",
            {
                "request": "Only my table",
                "context": {"row_count": None, "columns": [], "omissions": []},
                "aliases": [],
            },
        ),
    ]


@pytest.mark.parametrize("name", ["price", "1", "", "東京"])
def test_prompt_refuses_ambiguous_column_names(name: str) -> None:
    context = FilterContext(
        row_count=2,
        columns=[
            FilterContextColumn(
                name=name, type="string", source_type="String"
            ),
            FilterContextColumn(
                name=name, type="integer", source_type="Int64"
            ),
        ],
        omissions=[],
    )
    with pytest.raises(
        TableFilterContextError,
        match="duplicate column names",
    ):
        build_table_filter_prompt(context, "Keep the first column")


def test_reference_uses_every_catalog_operation() -> None:
    operations = DEFAULT_TABLE_FILTER_ASSETS.operations
    lines = build_table_filter_reference(operations).splitlines()
    assert [
        {
            "id": line.split(" ", 2)[1],
            "has_example": f"Example: {operation.example}." in line,
            "has_form": operation.fql_form in line,
            "has_operator": f"-> {operation.native_operator}:" in line,
            "has_types": f"[{', '.join(operation.supported_types)}]" in line,
        }
        for operation, line in zip(operations, lines, strict=True)
    ] == [
        {
            "id": operation.id,
            "has_example": True,
            "has_form": True,
            "has_operator": True,
            "has_types": True,
        }
        for operation in operations
    ]


def test_prompt_accepts_assets_without_file_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = (
        TableFilterOperation(
            id="custom_reference",
            fql_form='column="value"',
            example='label="**"',
            native_operator="equals",
            supported_types=("string",),
            meaning="Match literal text.",
        ),
    )
    assets = replace(DEFAULT_TABLE_FILTER_ASSETS, operations=operations)
    prefix = assets.suite.cases[0]
    suite = msgspec.structs.replace(
        assets.suite,
        cases=(
            msgspec.structs.replace(
                prefix, request="New request", fql="New FQL"
            ),
            *assets.suite.cases[1:],
        ),
    )
    assets = replace(assets, suite=suite)

    def refuse_read(path: Path) -> bytes:
        raise AssertionError(f"Pure construction read {path}")

    monkeypatch.setattr(Path, "read_bytes", refuse_read)
    prompt = build_table_filter_prompt(
        FilterContext(row_count=None, columns=[], omissions=[]),
        "My request",
        assets=assets,
    )
    assert {
        "reference": build_table_filter_reference(assets.operations),
        "included": build_table_filter_reference(assets.operations)
        in prompt.system_prompt,
        "first_request": prompt.messages[0]["parts"][0]["text"],
        "first_response": json.loads(prompt.messages[1]["parts"][0]["text"]),
    } == {
        "reference": '- custom_reference [string] -> equals: column="value". '
        'Example: label="**". Match literal text.',
        "included": True,
        "first_request": "New request",
        "first_response": {"fql": "New FQL", "explanation": None},
    }


@pytest.mark.parametrize(
    ("filename", "field", "invalid_value"),
    [
        ("table_filter_operation_catalog.json", "version", 2),
        (
            "table_filter_conformance_cases.json",
            "refusals",
            [{"id": "missing_column", "request": "No column"}],
        ),
    ],
)
def test_asset_loader_rejects_invalid_data(
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    field: str,
    invalid_value: object,
) -> None:
    read_bytes = Path.read_bytes

    def invalid_asset(path: Path) -> bytes:
        data = read_bytes(path)
        if path.name == filename:
            value = json.loads(data)
            value[field] = invalid_value
            return json.dumps(value).encode()
        return data

    monkeypatch.setattr(Path, "read_bytes", invalid_asset)
    with pytest.raises(msgspec.ValidationError):
        load_table_filter_assets()
