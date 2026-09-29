from __future__ import annotations

import csv
import zipfile
from typing import TYPE_CHECKING, Literal

from benchmarks.ai.models import (
    ExpectedValue,
    NumericExpectation,
    Scenario,
    ScenarioWorkspace,
)

if TYPE_CHECKING:
    from pathlib import Path


_EMPTY_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


if __name__ == "__main__":
    app.run()
"""


def _write_csv(
    path: Path, fieldnames: list[str], rows: list[dict[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_notebook(root: Path, source: str = _EMPTY_NOTEBOOK) -> Path:
    notebook = root / "analysis.py"
    notebook.write_text(source, encoding="utf-8")
    return notebook


def _workspace(
    root: Path,
    expected_summary: dict[str, ExpectedValue],
    *,
    notebook_source: str = _EMPTY_NOTEBOOK,
    required_source_fragments: tuple[str, ...] = (),
    forbidden_source_fragments: tuple[str, ...] = (),
    required_source_order: tuple[tuple[str, str], ...] = (),
) -> ScenarioWorkspace:
    return ScenarioWorkspace(
        notebook=_write_notebook(root, notebook_source),
        expected_summary=expected_summary,
        required_source_fragments=required_source_fragments,
        forbidden_source_fragments=forbidden_source_fragments,
        required_source_order=required_source_order,
    )


def _setup_athletes(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "athletes.csv",
        ["name", "sport", "nationality", "gold", "silver", "bronze"],
        [
            {
                "name": "Amina",
                "sport": "swimming",
                "nationality": "USA",
                "gold": 3,
                "silver": 1,
                "bronze": 0,
            },
            {
                "name": "Bea",
                "sport": "athletics",
                "nationality": "USA",
                "gold": 2,
                "silver": 2,
                "bronze": 1,
            },
            {
                "name": "Chen",
                "sport": "swimming",
                "nationality": "CHN",
                "gold": 2,
                "silver": 1,
                "bronze": 2,
            },
            {
                "name": "Dara",
                "sport": "cycling",
                "nationality": "GBR",
                "gold": 1,
                "silver": 2,
                "bronze": 1,
            },
        ],
    )
    return _workspace(root, {"top_nationality": "USA", "top_total_medals": 9})


def _setup_inventory(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "inventory.csv",
        ["sku", "on_hand", "reserved", "reported_available"],
        [
            {
                "sku": "A",
                "on_hand": 20,
                "reserved": 5,
                "reported_available": 15,
            },
            {
                "sku": "B",
                "on_hand": 12,
                "reserved": 4,
                "reported_available": 10,
            },
            {
                "sku": "C",
                "on_hand": 8,
                "reserved": 10,
                "reported_available": -2,
            },
            {
                "sku": "D",
                "on_hand": 15,
                "reserved": 3,
                "reported_available": 9,
            },
        ],
    )
    return _workspace(
        root,
        {
            "largest_discrepancy_sku": "D",
            "discrepant_sku_count": 2,
            "total_computed_available": 33,
        },
    )


_SUPPORT_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    import pandas as pd
    tickets = pd.read_csv("data/tickets.csv")
    return (tickets,)


@app.cell
def _(tickets):
    # This boundary condition is intentionally wrong.
    tickets["breached"] = tickets["resolution_hours"] >= tickets["sla_hours"]
    analysis_summary = {"breach_count": int(tickets["breached"].sum())}
    return (analysis_summary,)


if __name__ == "__main__":
    app.run()
"""


def _setup_support_tickets(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "tickets.csv",
        ["ticket_id", "team", "resolution_hours", "sla_hours"],
        [
            {
                "ticket_id": "t1",
                "team": "Core",
                "resolution_hours": 4,
                "sla_hours": 4,
            },
            {
                "ticket_id": "t2",
                "team": "Core",
                "resolution_hours": 6,
                "sla_hours": 4,
            },
            {
                "ticket_id": "t3",
                "team": "Data",
                "resolution_hours": 10,
                "sla_hours": 8,
            },
            {
                "ticket_id": "t4",
                "team": "Data",
                "resolution_hours": 3,
                "sla_hours": 4,
            },
            {
                "ticket_id": "t5",
                "team": "Core",
                "resolution_hours": 9,
                "sla_hours": 8,
            },
        ],
    )
    return _workspace(
        root,
        {"breach_count": 3, "worst_team": "Core"},
        notebook_source=_SUPPORT_NOTEBOOK,
    )


def _setup_retail(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "customers.csv",
        ["customer_id", "segment", "region", "is_internal"],
        [
            {
                "customer_id": "c1",
                "segment": "Enterprise",
                "region": "North",
                "is_internal": "false",
            },
            {
                "customer_id": "c2",
                "segment": "SMB",
                "region": "North",
                "is_internal": "false",
            },
            {
                "customer_id": "c3",
                "segment": "Enterprise",
                "region": "South",
                "is_internal": "false",
            },
            {
                "customer_id": "c4",
                "segment": "SMB",
                "region": "South",
                "is_internal": "true",
            },
            {
                "customer_id": "c5",
                "segment": "Mid-Market",
                "region": "West",
                "is_internal": "false",
            },
            {
                "customer_id": "c2",
                "segment": "SMB",
                "region": "North",
                "is_internal": "false",
            },
        ],
    )
    _write_csv(
        root / "data" / "orders.csv",
        ["order_id", "customer_id", "ordered_at", "gross_revenue"],
        [
            {
                "order_id": "o1",
                "customer_id": "c1",
                "ordered_at": "2026-02-05",
                "gross_revenue": 1000,
            },
            {
                "order_id": "o2",
                "customer_id": "c2",
                "ordered_at": "2026-03-10",
                "gross_revenue": 600,
            },
            {
                "order_id": "o3",
                "customer_id": "c3",
                "ordered_at": "2026-03-20",
                "gross_revenue": 800,
            },
            {
                "order_id": "o4",
                "customer_id": "c4",
                "ordered_at": "2026-03-28",
                "gross_revenue": 10000,
            },
            {
                "order_id": "o5",
                "customer_id": "c5",
                "ordered_at": "2026-01-17",
                "gross_revenue": 500,
            },
            {
                "order_id": "o6",
                "customer_id": "c1",
                "ordered_at": "2026-04-11",
                "gross_revenue": 700,
            },
            {
                "order_id": "o7",
                "customer_id": "c2",
                "ordered_at": "2026-05-09",
                "gross_revenue": 500,
            },
            {
                "order_id": "o8",
                "customer_id": "c3",
                "ordered_at": "2026-06-03",
                "gross_revenue": 400,
            },
            {
                "order_id": "o9",
                "customer_id": "c4",
                "ordered_at": "2026-05-19",
                "gross_revenue": 12000,
            },
            {
                "order_id": "o10",
                "customer_id": "c5",
                "ordered_at": "2026-06-21",
                "gross_revenue": 450,
            },
        ],
    )
    _write_csv(
        root / "data" / "returns.csv",
        ["order_id", "return_amount"],
        [
            {"order_id": "o2", "return_amount": 50},
            {"order_id": "o6", "return_amount": 100},
            {"order_id": "o8", "return_amount": 200},
        ],
    )
    return _workspace(
        root,
        {
            "q1_net_revenue": 2850.0,
            "q2_net_revenue": 1750.0,
            "absolute_change": -1100.0,
            "percent_change": NumericExpectation(-38.6, 0.05),
            "largest_declining_segment": "Enterprise",
        },
    )


def _setup_subscriptions(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "subscriptions.csv",
        ["subscription_id", "start_date", "cancelled_at", "mrr"],
        [
            {
                "subscription_id": "s1",
                "start_date": "2026-01-05",
                "cancelled_at": "",
                "mrr": 100,
            },
            {
                "subscription_id": "s2",
                "start_date": "01/20/2026",
                "cancelled_at": "2026-03-15",
                "mrr": 200,
            },
            {
                "subscription_id": "s3",
                "start_date": "2026/02/03",
                "cancelled_at": "",
                "mrr": 150,
            },
            {
                "subscription_id": "s4",
                "start_date": "not-a-date",
                "cancelled_at": "",
                "mrr": 500,
            },
            {
                "subscription_id": "s5",
                "start_date": "2026-03-01",
                "cancelled_at": "2026-02-28",
                "mrr": 300,
            },
        ],
    )
    return _workspace(
        root,
        {"active_mrr": 250, "january_activations": 2, "invalid_records": 2},
    )


def _setup_orders(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "products.csv",
        ["product_id", "category", "unit_price"],
        [
            {"product_id": "p1", "category": "Home ", "unit_price": 10},
            {"product_id": "p2", "category": "home", "unit_price": 20},
            {"product_id": "p3", "category": "", "unit_price": 15},
            {"product_id": "p4", "category": "Garden", "unit_price": ""},
        ],
    )
    _write_csv(
        root / "data" / "orders.csv",
        ["order_id", "product_id", "quantity"],
        [
            {"order_id": "o1", "product_id": "p1", "quantity": 2},
            {"order_id": "o2", "product_id": "p2", "quantity": 2},
            {"order_id": "o3", "product_id": "p3", "quantity": 3},
            {"order_id": "o4", "product_id": "p4", "quantity": 5},
        ],
    )
    return _workspace(
        root,
        {
            "top_category": "Home",
            "top_category_revenue": 60,
            "total_valid_revenue": 105,
            "excluded_order_count": 1,
        },
    )


_REACTIVE_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    import pandas as pd
    metrics = pd.read_csv("data/metrics.csv")
    return (metrics,)


@app.cell
def _():
    selected_region = "North"
    return (selected_region,)


@app.cell
def _(metrics, selected_region):
    regional = metrics[metrics["region"] == selected_region].copy()
    regional["change"] = regional["current"] - regional["baseline"]
    return (regional,)


@app.cell
def _(regional):
    analysis_summary = {"total_change": int(regional["change"].sum())}
    return (analysis_summary,)


if __name__ == "__main__":
    app.run()
"""


def _setup_reactive_repair(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "metrics.csv",
        ["region", "product", "baseline", "current"],
        [
            {
                "region": "North",
                "product": "A",
                "baseline": 100,
                "current": 105,
            },
            {"region": "North", "product": "B", "baseline": 60, "current": 70},
            {"region": "South", "product": "A", "baseline": 80, "current": 88},
            {"region": "South", "product": "B", "baseline": 50, "current": 45},
        ],
    )
    return _workspace(
        root,
        {
            "selected_region": "South",
            "total_change": 3,
            "top_improving_product": "A",
        },
        notebook_source=_REACTIVE_NOTEBOOK,
    )


def _setup_saas(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "accounts.csv",
        ["account_id", "plan", "is_trial"],
        [
            {"account_id": "a1", "plan": "Enterprise", "is_trial": "false"},
            {"account_id": "a2", "plan": "SMB", "is_trial": "true"},
            {"account_id": "a3", "plan": "SMB", "is_trial": "false"},
            {"account_id": "a4", "plan": "Enterprise", "is_trial": "false"},
        ],
    )
    _write_csv(
        root / "data" / "invoices.csv",
        ["invoice_id", "account_id", "invoice_date", "status", "amount"],
        [
            {
                "invoice_id": "i1",
                "account_id": "a1",
                "invoice_date": "2026-01-10",
                "status": "paid",
                "amount": 1000,
            },
            {
                "invoice_id": "i2",
                "account_id": "a2",
                "invoice_date": "2026-01-20",
                "status": "paid",
                "amount": 900,
            },
            {
                "invoice_id": "i3",
                "account_id": "a3",
                "invoice_date": "2026-02-14",
                "status": "paid",
                "amount": 400,
            },
            {
                "invoice_id": "i4",
                "account_id": "a4",
                "invoice_date": "2026-03-08",
                "status": "unpaid",
                "amount": 800,
            },
            {
                "invoice_id": "i5",
                "account_id": "a1",
                "invoice_date": "2026-04-03",
                "status": "paid",
                "amount": 500,
            },
        ],
    )
    return _workspace(
        root,
        {
            "q1_collected_revenue": 1400,
            "top_plan": "Enterprise",
            "top_plan_revenue": 1000,
            "excluded_trial_revenue": 900,
            "unpaid_revenue": 800,
        },
    )


def _setup_operations(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "warehouses.csv",
        ["warehouse_id", "region", "is_test"],
        [
            {"warehouse_id": "w1", "region": "North", "is_test": "false"},
            {"warehouse_id": "w2", "region": "South", "is_test": "false"},
            {"warehouse_id": "w3", "region": "Lab", "is_test": "true"},
        ],
    )
    _write_csv(
        root / "data" / "shipments.csv",
        [
            "shipment_id",
            "warehouse_id",
            "carrier",
            "promised_date",
            "delivered_date",
        ],
        [
            {
                "shipment_id": "s1",
                "warehouse_id": "w1",
                "carrier": "Air",
                "promised_date": "2026-01-10",
                "delivered_date": "2026-01-11",
            },
            {
                "shipment_id": "s2",
                "warehouse_id": "w1",
                "carrier": "Ground",
                "promised_date": "2026-01-12",
                "delivered_date": "2026-01-12",
            },
            {
                "shipment_id": "s3",
                "warehouse_id": "w2",
                "carrier": "Air",
                "promised_date": "2026-01-05",
                "delivered_date": "2026-01-08",
            },
            {
                "shipment_id": "s4",
                "warehouse_id": "w3",
                "carrier": "Ground",
                "promised_date": "2026-01-01",
                "delivered_date": "2026-01-10",
            },
            {
                "shipment_id": "s5",
                "warehouse_id": "w2",
                "carrier": "Ground",
                "promised_date": "2026-01-20",
                "delivered_date": "",
            },
        ],
    )
    return _workspace(
        root,
        {
            "late_rate_percent": NumericExpectation(66.7, 0.05),
            "worst_carrier": "Air",
            "maximum_delay_days": 3,
            "excluded_test_shipments": 1,
            "open_shipments": 1,
        },
    )


def _write_local_wheel(
    root: Path,
    *,
    distribution: str,
    module: str,
    source: str,
) -> Path:
    """Create a deterministic pure-Python wheel without build dependencies."""
    version = "0.1.0"
    wheel = root / "packages" / f"{distribution}-{version}-py3-none-any.whl"
    wheel.parent.mkdir(parents=True, exist_ok=True)
    dist_info = f"{distribution}-{version}.dist-info"
    contents = {
        f"{module}/__init__.py": source,
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {distribution.replace('_', '-')}\n"
            f"Version: {version}\n"
        ),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: marimo-ai-eval\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ),
    }
    record = "".join(f"{path},,\n" for path in contents)
    contents[f"{dist_info}/RECORD"] = record + f"{dist_info}/RECORD,,\n"
    with zipfile.ZipFile(wheel, "w") as archive:
        for path, value in contents.items():
            archive.writestr(path, value)
    return wheel


def _setup_package_lifecycle(root: Path) -> ScenarioWorkspace:
    _write_local_wheel(
        root,
        distribution="eval_transformer",
        module="eval_transformer",
        source=(
            "def trimmed_mean(values):\n"
            "    ordered = sorted(values)\n"
            "    return sum(ordered[1:-1]) / len(ordered[1:-1])\n"
        ),
    )
    _write_local_wheel(
        root,
        distribution="eval_robust",
        module="eval_robust",
        source=(
            "import statistics\n\n"
            "def median_absolute_deviation(values):\n"
            "    center = statistics.median(values)\n"
            "    return statistics.median(abs(value - center) for value in values)\n"
        ),
    )
    return _workspace(
        root,
        {
            "package_name": "eval-robust",
            "robust_center": 2.5,
            "median_absolute_deviation": 1.0,
        },
        required_source_fragments=(
            "from eval_robust import median_absolute_deviation",
        ),
        forbidden_source_fragments=("eval_transformer",),
    )


_UI_STATE_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    multiplier = mo.ui.slider(1, 5, value=2, label="Multiplier")
    multiplier
    return (multiplier,)


@app.cell
def _(multiplier):
    analysis_summary = {
        "selected_multiplier": multiplier.value,
        "scaled_total": 10 * multiplier.value,
    }
    return (analysis_summary,)


if __name__ == "__main__":
    app.run()
"""


def _setup_ui_state(root: Path) -> ScenarioWorkspace:
    return _workspace(
        root,
        {"selected_multiplier": 4, "scaled_total": 40},
        notebook_source=_UI_STATE_NOTEBOOK,
        required_source_fragments=("value=2",),
        forbidden_source_fragments=("value=4",),
    )


_LAYOUT_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def load_data():
    values = [1, 2, 3]
    return (values,)


@app.cell
def chart(values):
    chart_output = {"kind": "bar", "values": values}
    chart_output
    return (chart_output,)


@app.cell
def summary(values):
    analysis_summary = {"total": sum(values)}
    analysis_summary
    return (analysis_summary,)


if __name__ == "__main__":
    app.run()
"""


def _setup_layout_configuration(root: Path) -> ScenarioWorkspace:
    return _workspace(
        root,
        {"total": 6},
        notebook_source=_LAYOUT_NOTEBOOK,
        required_source_fragments=("hide_code=True", "expand_output=True"),
        required_source_order=(("def summary", "def chart"),),
    )


_SUMMARY_CONTRACT = """Keep the analysis reproducible and validate inputs and
totals before drawing a conclusion. Store the final headline values in a public
dictionary named `analysis_summary`; do not estimate them from a chart. Display
the supporting table or chart and summarize the conclusion in your response."""


SCENARIOS = (
    Scenario(
        id="athletes_prescribed",
        description="Prescribed aggregation and visualization smoke test.",
        length="short",
        failure_modes=("instruction_following", "notebook_authoring"),
        setup=_setup_athletes,
        turns=(
            """Work in the active marimo notebook. Load data/athletes.csv, sum
gold, silver, and bronze medals by nationality, rank countries by total medals,
and create an Altair bar chart sorted highest to lowest. Store the leader in
`analysis_summary` under `top_nationality` and `top_total_medals`.

"""
            + _SUMMARY_CONTRACT,
        ),
    ),
    Scenario(
        id="inventory_schema_inspection",
        description="Small audit requiring schema inspection and derived values.",
        length="short",
        failure_modes=("schema_inspection", "arithmetic_validation"),
        setup=_setup_inventory,
        turns=(
            """Audit data/inventory.csv in the active notebook. Compute available
as on_hand minus reserved, find discrepancies with reported_available, and show
a compact table. Store `largest_discrepancy_sku`, `discrepant_sku_count`, and
`total_computed_available` in `analysis_summary`.

"""
            + _SUMMARY_CONTRACT,
        ),
    ),
    Scenario(
        id="support_ticket_targeted_repair",
        description="Targeted correction of an existing notebook.",
        length="short",
        failure_modes=("existing_code_edit", "boundary_condition"),
        setup=_setup_support_tickets,
        turns=(
            """Repair the existing ticket analysis. An SLA is breached only when
resolution_hours is strictly greater than sla_hours. Preserve the useful
structure, add a team comparison, and set `analysis_summary` to
`breach_count` and `worst_team`.

"""
            + _SUMMARY_CONTRACT,
        ),
    ),
    Scenario(
        id="retail_investigation_short",
        description="Open-ended, multi-table retail investigation.",
        length="medium",
        failure_modes=("unsafe_join", "filtering", "returns_accounting"),
        setup=_setup_retail,
        turns=(
            """Work in the active notebook. Analyze why net revenue changed from
Q1 to Q2 2026 using `data/customers.csv`, `data/orders.csv`, and
`data/returns.csv`. Exclude internal customers, account for returns, identify
the segment with the largest decline, visualize it, and guard against duplicate
customer rows. Set `analysis_summary` with
`q1_net_revenue`, `q2_net_revenue`, `absolute_change`, `percent_change`, and
`largest_declining_segment`. Express `percent_change` in percentage points,
so a 12.5% increase is stored as `12.5`, not `0.125`.

"""
            + _SUMMARY_CONTRACT,
        ),
    ),
    Scenario(
        id="subscriptions_dirty_dates",
        description="Date normalization and invalid lifecycle records.",
        length="medium",
        failure_modes=("mixed_date_formats", "invalid_records", "time_window"),
        setup=_setup_subscriptions,
        turns=(
            """Analyze data/subscriptions.csv as of 2026-03-31. Normalize mixed
date formats. Treat an invalid start date or cancellation before start as an
invalid record and exclude it from business metrics. A subscription is active
when it started by the as-of date and has no cancellation on or before it.
Report active MRR, valid January activations, and invalid record count in
`analysis_summary` as `active_mrr`, `january_activations`, `invalid_records`.

"""
            + _SUMMARY_CONTRACT,
        ),
    ),
    Scenario(
        id="orders_missing_dimensions",
        description="Join with missing dimensions and normalized categories.",
        length="medium",
        failure_modes=(
            "missing_values",
            "category_normalization",
            "join_validation",
        ),
        setup=_setup_orders,
        turns=(
            """Analyze products and orders. Normalize category whitespace and
case to title case, label missing categories Unknown, and exclude orders whose
unit price is missing. Chart revenue by category. Set `analysis_summary` with
`top_category`, `top_category_revenue`, `total_valid_revenue`, and
`excluded_order_count`.

"""
            + _SUMMARY_CONTRACT,
        ),
    ),
    Scenario(
        id="reactive_dependency_repair",
        description="Modify an existing reactive analysis without duplicate definitions.",
        length="medium",
        failure_modes=(
            "reactive_dependencies",
            "existing_code_edit",
            "duplicate_names",
        ),
        setup=_setup_reactive_repair,
        turns=(
            """Update the existing notebook to analyze South instead of North.
Repair downstream output in place without duplicate variable definitions, add
a product-level comparison, and set `analysis_summary` with `selected_region`,
`total_change`, and `top_improving_product`.

"""
            + _SUMMARY_CONTRACT,
        ),
    ),
    Scenario(
        id="retail_investigation_long",
        description="Retail requirements disclosed and corrected over six turns.",
        length="long",
        failure_modes=(
            "context_retention",
            "requirement_revision",
            "unsafe_join",
        ),
        setup=_setup_retail,
        turns=(
            "Explore `data/customers.csv`, `data/orders.csv`, and `data/returns.csv`, then compare Q1 and Q2 2026 revenue reproducibly.",
            "Break the change down by customer segment.",
            "Exclude internal test customers from every calculation.",
            "Use net revenue after returns. Update the analysis in place.",
            "Visualize segment change and verify the customer join did not duplicate revenue.",
            "Finish with `analysis_summary`: `q1_net_revenue`, `q2_net_revenue`, `absolute_change`, `percent_change`, and `largest_declining_segment`. Express `percent_change` in percentage points, so a 12.5% increase is stored as `12.5`, not `0.125`.",
        ),
    ),
    Scenario(
        id="saas_requirement_reversal",
        description="Revenue definition is progressively narrowed over six turns.",
        length="long",
        failure_modes=(
            "context_retention",
            "requirement_revision",
            "filtering",
        ),
        setup=_setup_saas,
        turns=(
            "Explore accounts and invoices and summarize revenue by plan.",
            "Use collected revenue, meaning paid invoices only, instead of all invoiced revenue.",
            "Trial accounts must be excluded from the headline metric, but quantify what was excluded.",
            "Restrict the headline analysis to Q1 2026; retain unpaid Q1 revenue as a validation metric.",
            "Add a plan comparison and validate that account joins preserve invoice totals.",
            "Set `analysis_summary` to `q1_collected_revenue`, `top_plan`, `top_plan_revenue`, `excluded_trial_revenue`, and `unpaid_revenue`.",
        ),
    ),
    Scenario(
        id="operations_context_pressure",
        description="Early metric rules must survive a long operational investigation.",
        length="long",
        failure_modes=(
            "context_retention",
            "exclusion_rules",
            "date_arithmetic",
        ),
        setup=_setup_operations,
        turns=(
            "Investigate shipment punctuality using `data/shipments.csv` and `data/warehouses.csv`. Late means delivered after the promised calendar date. Use completed shipments only and exclude test warehouses.",
            "Break punctuality down by carrier and region.",
            "Show the distribution of delay days; on-time shipments have zero delay.",
            "Also quantify test-warehouse shipments and open shipments, but keep both outside the late-rate denominator.",
            "Check the join cardinality and make the notebook easy to audit.",
            "Add a useful carrier visualization without removing the validation tables.",
            "Set `analysis_summary` to a dictionary with `late_rate_percent` rounded to one decimal, `worst_carrier`, `maximum_delay_days`, `excluded_test_shipments`, and `open_shipments`. The last two values must be integer counts, not shipment ID lists.",
        ),
    ),
)


CAPABILITY_SCENARIOS = (
    Scenario(
        id="package_lifecycle",
        description="Install, replace, and remove local notebook dependencies.",
        length="medium",
        failure_modes=(
            "package_installation",
            "package_removal",
            "requirement_revision",
        ),
        setup=_setup_package_lifecycle,
        isolated_environment=True,
        turns=(
            """Install the local wheel
packages/eval_transformer-0.1.0-py3-none-any.whl through marimo notebook
package management. Use `eval_transformer.trimmed_mean` on
`[1, 2, 3, 100]` in a reproducible notebook cell.""",
            """Replace that dependency with
packages/eval_robust-0.1.0-py3-none-any.whl and remove `eval-transformer`.
Update the notebook in place to import `median_absolute_deviation` from
`eval_robust`. Set `analysis_summary` to a dictionary with the keys
`package_name` (`eval-robust`), `robust_center`, and
`median_absolute_deviation` for `[1, 2, 3, 100]`.""",
        ),
    ),
    Scenario(
        id="ui_state_interaction",
        description="Change live UI state without rewriting widget source.",
        length="short",
        failure_modes=("ui_interaction", "reactive_execution"),
        setup=_setup_ui_state,
        turns=(
            """Set the live `multiplier` UI element to 4 and verify its
reactive downstream result. Do not edit the slider's source or default value.
Finish only when `analysis_summary` reports the selected multiplier and scaled
total from the live UI state.""",
        ),
    ),
    Scenario(
        id="cell_layout_configuration",
        description="Change presentation metadata and visual cell ordering.",
        length="short",
        failure_modes=("cell_configuration", "visual_ordering"),
        setup=_setup_layout_configuration,
        turns=(
            """Keep the notebook computation unchanged. Hide the code for the
`load_data` cell, expand the output of the `chart` cell, and move the chart
cell so it appears directly after the `summary` cell. Verify that
`analysis_summary` still reports the same total.""",
        ),
    ),
)


_QUICK_SCENARIO_IDS = {
    "athletes_prescribed",
    "retail_investigation_short",
}


def get_scenarios(
    ids: set[str] | None = None,
    *,
    suite: Literal["quick", "full", "capabilities", "all"] = "full",
) -> tuple[Scenario, ...]:
    all_scenarios = (*SCENARIOS, *CAPABILITY_SCENARIOS)
    selected_ids = ids
    if selected_ids is None and suite == "quick":
        selected_ids = _QUICK_SCENARIO_IDS
    if selected_ids is None and suite == "full":
        return SCENARIOS
    if selected_ids is None and suite == "capabilities":
        return CAPABILITY_SCENARIOS
    if selected_ids is None and suite == "all":
        return all_scenarios
    assert selected_ids is not None
    scenarios = tuple(
        scenario for scenario in all_scenarios if scenario.id in selected_ids
    )
    missing = selected_ids - {scenario.id for scenario in scenarios}
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"Unknown scenario(s): {names}")
    return scenarios
