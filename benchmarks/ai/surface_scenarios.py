from __future__ import annotations

import csv
from typing import TYPE_CHECKING, Literal, TypeVar

from benchmarks.ai.surface_models import (
    GenerateScenario,
    GenerateWorkspace,
    InlineScenario,
)

if TYPE_CHECKING:
    from pathlib import Path


_EMPTY_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


if __name__ == "__main__":
    app.run()
"""


def _notebook(root: Path) -> Path:
    path = root / "analysis.py"
    path.write_text(_EMPTY_NOTEBOOK, encoding="utf-8")
    return path


def _setup_generate_sales(root: Path) -> GenerateWorkspace:
    data = root / "data"
    data.mkdir()
    with (data / "sales.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["region", "gross", "returns"])
        writer.writerows(
            [
                ["North", 140, 10],
                ["South", 90, 5],
                ["North", 80, 0],
                ["West", 110, 20],
            ]
        )
    return GenerateWorkspace(
        notebook=_notebook(root),
        prompt=(
            "Generate exactly three Python cells for a marimo notebook. "
            "Load data/sales.csv with pandas, define row-level net revenue "
            "as gross minus returns, and calculate net revenue by region. "
            "Then create analysis_summary with top_region and "
            "total_net_revenue. Do not invent data."
        ),
        expected_summary={"top_region": "North", "total_net_revenue": 385},
        context_plain_text=(
            "data/sales.csv has columns region, gross, and returns."
        ),
        minimum_python_cells=3,
        maximum_python_cells=3,
        required_source_patterns=(r"read_csv\([\"']data/sales\.csv[\"']\)",),
    )


def _setup_generate_context(root: Path) -> GenerateWorkspace:
    existing = """orders = [
    {"status": "paid", "amount": 120.0},
    {"status": "refunded", "amount": 40.0},
    {"status": "paid", "amount": 80.0},
]
fee_rate = 0.025
"""
    return GenerateWorkspace(
        notebook=_notebook(root),
        prompt=(
            "Using the existing orders and fee_rate variables, generate two "
            "Python cells. Keep paid orders only, then set analysis_summary "
            "to paid_count and net_after_fees."
        ),
        expected_summary={"paid_count": 2, "net_after_fees": 195.0},
        prelude=existing,
        include_other_code=existing,
        minimum_python_cells=2,
        maximum_python_cells=2,
        forbidden_source_patterns=(
            r"(?m)^orders\s*=",
            r"(?m)^fee_rate\s*=",
        ),
    )


def _setup_generate_long(root: Path) -> GenerateWorkspace:
    data = root / "data"
    data.mkdir()
    with (data / "events.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["account", "event", "value", "is_test"])
        writer.writerows(
            [
                ["a", "activate", 10, "false"],
                ["a", "purchase", 25, "false"],
                ["b", "activate", 8, "false"],
                ["b", "purchase", 12, "true"],
                ["c", "activate", 6, "false"],
                ["c", "cancel", -2, "false"],
                ["d", "purchase", 30, "false"],
            ]
        )
    return GenerateWorkspace(
        notebook=_notebook(root),
        prompt=(
            "Build a four-cell Python analysis of data/events.csv. Exclude "
            "rows where is_test is true. An activated account is an account "
            "with at least one activate event; do not infer activation from "
            "purchase. Sum value only for the retained rows. In the final "
            "cell set analysis_summary to activated_accounts, "
            "activated_value, and highest_value_account. Break ties for the "
            "highest account alphabetically. Keep intermediate tables in "
            "separate cells and do not embed or recreate the fixture data."
        ),
        expected_summary={
            "activated_accounts": 3,
            "activated_value": 47,
            "highest_value_account": "a",
        },
        context_plain_text=(
            "data/events.csv has columns account, event, value, and is_test."
        ),
        minimum_python_cells=4,
        maximum_python_cells=4,
        required_source_patterns=(r"read_csv\([\"']data/events\.csv[\"']\)",),
    )


GENERATE_SCENARIOS = (
    GenerateScenario(
        id="generate_sales_pipeline",
        description="Generate a prescribed multi-cell CSV analysis.",
        length="short",
        failure_modes=("invented_data", "wrong_cell_count", "aggregation"),
        setup=_setup_generate_sales,
    ),
    GenerateScenario(
        id="generate_existing_context",
        description="Generate cells that reuse supplied notebook variables.",
        length="medium",
        failure_modes=("context_ignored", "variable_redefinition", "fees"),
        setup=_setup_generate_context,
    ),
    GenerateScenario(
        id="generate_requirements_long",
        description="Retain several data semantics across a long request.",
        length="long",
        failure_modes=(
            "requirement_loss",
            "test_data_leakage",
            "invented_data",
            "tie_breaking",
        ),
        setup=_setup_generate_long,
    ),
)


INLINE_SCENARIOS = (
    InlineScenario(
        id="inline_filter_expression",
        description="Complete a list-comprehension predicate.",
        length="short",
        failure_modes=("syntax", "prefix_duplication", "wrong_predicate"),
        prefix="values = [3, 8, 11, 14]\neven = [value for value in values ",
        suffix=']\nanalysis_summary = {"even": even}',
        expected_summary={"even": [8, 14]},
        required_completion_patterns=(r"\bif\b",),
    ),
    InlineScenario(
        id="inline_function_body",
        description="Complete an indented function body before a suffix.",
        length="medium",
        failure_modes=("indentation", "suffix_duplication", "wrong_formula"),
        prefix="def normalize(value, maximum):\n    ",
        suffix=('\n\nanalysis_summary = {"normalized": normalize(15, 20)}'),
        expected_summary={"normalized": 0.75},
        required_completion_patterns=(r"return",),
    ),
    InlineScenario(
        id="inline_long_context",
        description="Select the correct variables from a longer prefix.",
        length="long",
        failure_modes=("context_confusion", "suffix_duplication", "rounding"),
        prefix=(
            "subtotal = 240.0\n"
            "discount_rate = 0.15\n"
            "tax_rate = 0.08\n"
            "shipping = 12.0\n"
            "# Apply discount before tax, then add shipping.\n"
            "discounted = subtotal * (1 - discount_rate)\n"
            "total = "
        ),
        suffix=('\nanalysis_summary = {"total": round(total, 2)}'),
        expected_summary={"total": 232.32},
        forbidden_completion_fragments=("analysis_summary", "total ="),
    ),
)

SurfaceScenario = TypeVar("SurfaceScenario", GenerateScenario, InlineScenario)


def get_generate_scenarios(
    selected: set[str] | None = None,
) -> tuple[GenerateScenario, ...]:
    return _select(GENERATE_SCENARIOS, selected, surface="generate")


def get_inline_scenarios(
    selected: set[str] | None = None,
) -> tuple[InlineScenario, ...]:
    return _select(INLINE_SCENARIOS, selected, surface="inline")


def _select(
    scenarios: tuple[SurfaceScenario, ...],
    selected: set[str] | None,
    *,
    surface: Literal["generate", "inline"],
) -> tuple[SurfaceScenario, ...]:
    if selected is None:
        return scenarios
    known = {scenario.id for scenario in scenarios}
    unknown = selected - known
    if unknown:
        raise ValueError(
            f"Unknown {surface} scenario(s): {', '.join(sorted(unknown))}"
        )
    return tuple(scenario for scenario in scenarios if scenario.id in selected)
