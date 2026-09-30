from __future__ import annotations

import csv
import zipfile
from typing import TYPE_CHECKING, Literal

from benchmarks.ai.models import (
    ExpectedValue,
    FileAttachment,
    LiveCellEdit,
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
    required_source_patterns: tuple[str, ...] = (),
    forbidden_source_fragments: tuple[str, ...] = (),
    required_source_order: tuple[tuple[str, str], ...] = (),
    required_exact_cell_sources: tuple[str, ...] = (),
    turn_attachments: dict[int, tuple[FileAttachment, ...]] | None = None,
) -> ScenarioWorkspace:
    return ScenarioWorkspace(
        notebook=_write_notebook(root, notebook_source),
        expected_summary=expected_summary,
        required_source_fragments=required_source_fragments,
        required_source_patterns=required_source_patterns,
        forbidden_source_fragments=forbidden_source_fragments,
        required_source_order=required_source_order,
        required_exact_cell_sources=required_exact_cell_sources,
        turn_attachments=turn_attachments or {},
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


_HISTORICAL_RESTORE_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    raw_scores = [3, 18, 27, 42, 88, 130]
    return (raw_scores,)


@app.cell
def _(raw_scores):
    _bounded_scores = [max(12, min(_score, 91)) for _score in raw_scores]
    quality_score = round(sum(_bounded_scores) / len(_bounded_scores), 3)
    analysis_summary = {
        "method": "bounded-12-91",
        "quality_score": quality_score,
    }
    return (analysis_summary, quality_score)


if __name__ == "__main__":
    app.run()
"""

_HISTORICAL_RESTORE_CELL_SOURCE = """_bounded_scores = [max(12, min(_score, 91)) for _score in raw_scores]
quality_score = round(sum(_bounded_scores) / len(_bounded_scores), 3)
analysis_summary = {
    "method": "bounded-12-91",
    "quality_score": quality_score,
}"""


def _setup_historical_restore(root: Path) -> ScenarioWorkspace:
    return _workspace(
        root,
        {"method": "bounded-12-91", "quality_score": 46.333},
        notebook_source=_HISTORICAL_RESTORE_NOTEBOOK,
        required_source_fragments=('"method": "bounded-12-91"',),
        required_source_patterns=(r"max\(12,\s*min\([A-Za-z_]\w*,\s*91\)\)",),
        forbidden_source_fragments=("statistics.median", "trimmed_mean"),
        required_exact_cell_sources=(_HISTORICAL_RESTORE_CELL_SOURCE,),
    )


def _large_reactive_notebook() -> str:
    cells = [
        """@app.cell
def _():
    seed = 10
    return (seed,)
"""
    ]
    for index in range(1, 25):
        previous = "seed" if index == 1 else f"stage_{index - 1}"
        increment = 90 if index == 13 else index
        cells.append(
            f"""@app.cell
def _({previous}):
    stage_{index} = {previous} + {increment}
    return (stage_{index},)
"""
        )
    cells.append(
        """@app.cell
def _(stage_8, stage_16, stage_24):
    checkpoints = {"stage_8": stage_8, "stage_16": stage_16}
    analysis_summary = {
        "stage_8": stage_8,
        "stage_16": stage_16,
        "final_value": stage_24,
    }
    return (analysis_summary, checkpoints)
"""
    )
    return (
        'import marimo\n\n__generated_with = "0.25.0"\n'
        "app = marimo.App()\n\n\n"
        + "\n\n".join(cells)
        + '\n\nif __name__ == "__main__":\n    app.run()\n'
    )


def _setup_large_reactive_graph(root: Path) -> ScenarioWorkspace:
    return _workspace(
        root,
        {"stage_8": 46, "stage_16": 146, "final_value": 310},
        notebook_source=_large_reactive_notebook(),
        required_source_fragments=("stage_13 = stage_12 + 13",),
        required_source_patterns=(
            (
                r"(?:[\"']stage_24[\"']\s*:\s*stage_24|"
                r"checkpoints\[[\"']stage_24[\"']\]\s*=\s*stage_24)"
            ),
        ),
        forbidden_source_fragments=("stage_13 = stage_12 + 90",),
    )


_MIXED_CAPABILITY_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def imports():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def controls(mo):
    multiplier = mo.ui.slider(1, 5, value=2, label="Multiplier")
    multiplier
    return (multiplier,)


@app.cell
def load_data(pd):
    measurements = pd.read_csv("data/measurements.csv")
    return (measurements,)


@app.cell
def summary(measurements, multiplier):
    scaled_total = float(measurements["value"].sum() * multiplier.value)
    analysis_summary = {
        "selected_multiplier": multiplier.value,
        "scaled_total": scaled_total,
    }
    analysis_summary
    return (analysis_summary,)


if __name__ == "__main__":
    app.run()
"""


def _setup_mixed_capabilities(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "measurements.csv",
        ["value"],
        [{"value": 4}, {"value": 7}, {"value": 9}],
    )
    _write_local_wheel(
        root,
        distribution="eval_scaler",
        module="eval_scaler",
        source=(
            "def scaled_total(values, multiplier):\n"
            "    return float(sum(values) * multiplier)\n"
        ),
    )
    return _workspace(
        root,
        {
            "package_name": "eval-scaler",
            "selected_multiplier": 4,
            "scaled_total": 80.0,
        },
        notebook_source=_MIXED_CAPABILITY_NOTEBOOK,
        required_source_fragments=(
            "eval_scaler.scaled_total",
            '"package_name": "eval-scaler"',
            "value=2",
            "hide_code=True",
        ),
        forbidden_source_fragments=("value=4",),
        required_source_order=(("def controls", "def load_data"),),
    )


def _setup_campaign_clarification(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "campaigns.csv",
        ["campaign", "segment", "spend", "booked", "collected", "internal"],
        [
            {
                "campaign": "alpha",
                "segment": "SMB",
                "spend": 100,
                "booked": 260,
                "collected": 220,
                "internal": "false",
            },
            {
                "campaign": "beta",
                "segment": "Enterprise",
                "spend": 200,
                "booked": 500,
                "collected": 360,
                "internal": "false",
            },
            {
                "campaign": "demo",
                "segment": "Internal",
                "spend": 50,
                "booked": 1000,
                "collected": 1000,
                "internal": "true",
            },
            {
                "campaign": "gamma",
                "segment": "SMB",
                "spend": 150,
                "booked": 300,
                "collected": 180,
                "internal": "false",
            },
        ],
    )
    return _workspace(
        root,
        {
            "revenue_basis": "collected",
            "total_spend": 450,
            "total_revenue": 760,
            "roas": NumericExpectation(1.6889, 0.0001),
            "top_segment": "SMB",
        },
    )


_LIVE_EDIT_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def load_orders():
    import pandas as pd
    orders = pd.read_csv("data/orders.csv")
    return orders, pd


@app.cell
def policy(orders):
    eligible_orders = orders[orders["status"] == "paid"].copy()
    revenue_policy = "paid-only"
    return eligible_orders, revenue_policy


@app.cell
def summary(eligible_orders, revenue_policy):
    analysis_summary = {
        "revenue_policy": revenue_policy,
        "total_revenue": float(eligible_orders["revenue"].sum()),
    }
    analysis_summary
    return (analysis_summary,)


if __name__ == "__main__":
    app.run()
"""


_LIVE_POLICY_EDIT = """eligible_orders = orders[
    orders["status"].isin(["paid", "settled"])
].copy()
revenue_policy = "paid-and-settled"
"""


def _setup_live_human_edit(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "orders.csv",
        ["order_id", "region", "status", "revenue"],
        [
            {
                "order_id": "o1",
                "region": "East",
                "status": "paid",
                "revenue": 120,
            },
            {
                "order_id": "o2",
                "region": "West",
                "status": "settled",
                "revenue": 150,
            },
            {
                "order_id": "o3",
                "region": "East",
                "status": "paid",
                "revenue": 180,
            },
            {
                "order_id": "o4",
                "region": "West",
                "status": "open",
                "revenue": 900,
            },
        ],
    )
    return _workspace(
        root,
        {
            "revenue_policy": "paid-and-settled",
            "total_revenue": 450.0,
            "top_region": "East",
        },
        notebook_source=_LIVE_EDIT_NOTEBOOK,
        required_source_fragments=("paid-and-settled", "top_region"),
    )


_VISUAL_REVIEW_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    import altair as alt
    import pandas as pd
    return alt, pd


@app.cell
def _(pd):
    revenue = pd.DataFrame(
        {
            "product": [
                "Team Collaboration Suite",
                "Enterprise Analytics Platform",
                "Workflow Automation Studio",
                "Customer Intelligence Cloud",
            ],
            "revenue": [42, 91, 58, 73],
        }
    )
    return (revenue,)


@app.cell
def _(alt, revenue):
    chart = (
        alt.Chart(revenue)
        .mark_bar()
        .encode(
            x=alt.X("product:N", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("revenue:Q"),
        )
        .properties(width=240, title="Revenue by product")
    )
    chart
    return (chart,)


@app.cell
def _(revenue):
    analysis_summary = {
        "top_product": revenue.loc[revenue["revenue"].idxmax(), "product"],
        "total_revenue": int(revenue["revenue"].sum()),
    }
    return (analysis_summary,)


if __name__ == "__main__":
    app.run()
"""


def _write_visual_review_image(path: Path) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (900, 560), "white")
    draw = ImageDraw.Draw(image)
    draw.text((32, 22), "DESIGN REVIEW: Revenue by product", fill="#111827")
    baseline = 380
    products = (
        "Team Collaboration",
        "Enterprise Analytics",
        "Workflow Automation",
        "Customer Intelligence",
    )
    values = (42, 91, 58, 73)
    for index, (product, value) in enumerate(
        zip(products, values, strict=True)
    ):
        left = 70 + index * 115
        top = baseline - value * 3
        draw.rectangle((left, top, left + 72, baseline), fill="#4c78a8")
        # Horizontal labels deliberately collide, matching the notebook bug.
        draw.text((left - 8, baseline + 8), product, fill="#111827")
    draw.line((55, baseline, 545, baseline), fill="#111827", width=2)
    draw.rounded_rectangle(
        (585, 90, 870, 360),
        radius=14,
        fill="#fff1f2",
        outline="#e11d48",
        width=3,
    )
    draw.text((610, 118), "REQUIRED FIXES", fill="#9f1239")
    draw.text((610, 165), "1. Sort bars high to low", fill="#111827")
    draw.text((610, 205), "2. Rotate labels to -35 deg", fill="#111827")
    draw.text((610, 245), "3. Widen chart to 650 px", fill="#111827")
    draw.line((600, 295, 520, 410), fill="#e11d48", width=4)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def _setup_static_visual_review(root: Path) -> ScenarioWorkspace:
    image = root / "fixtures" / "visual-review.png"
    _write_visual_review_image(image)
    return _workspace(
        root,
        {
            "top_product": "Enterprise Analytics Platform",
            "total_revenue": 264,
        },
        notebook_source=_VISUAL_REVIEW_NOTEBOOK,
        required_source_fragments=(
            "labelAngle=-35",
            "width=650",
        ),
        required_source_patterns=(
            (
                r"(?:sort\s*=\s*[\"']-y[\"']|"
                r"sort_values\([\"']revenue[\"'],\s*ascending=False\))"
            ),
            r"\n\s+chart\s*\n\s+return",
        ),
        forbidden_source_fragments=("width=240", "labelAngle=0"),
        turn_attachments={
            1: (
                FileAttachment(
                    path=image,
                    media_type="image/png",
                    filename="visual-review.png",
                ),
            )
        },
    )


_RENDERED_OUTPUT_REVIEW_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    import altair as alt
    import marimo as mo
    import pandas as pd
    return alt, mo, pd


@app.cell
def _(mo):
    review_card = mo.image("fixtures/rendered-output-review.png")
    review_card
    return (review_card,)


@app.cell
def _(pd):
    revenue = pd.DataFrame(
        {
            "product": ["Alpha", "Beta", "Gamma"],
            "revenue": [60, 75, 100],
        }
    )
    return (revenue,)


@app.cell
def _(alt, revenue):
    chart = (
        alt.Chart(revenue)
        .mark_bar()
        .encode(
            x=alt.X("product:N", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("revenue:Q"),
        )
        .properties(width=300, title="Revenue")
    )
    chart
    return (chart,)


@app.cell
def _(revenue):
    analysis_summary = {
        "top_product": revenue.loc[revenue["revenue"].idxmax(), "product"],
        "total_revenue": int(revenue["revenue"].sum()),
        "review_code": "pending",
    }
    return (analysis_summary,)


if __name__ == "__main__":
    app.run()
"""


def _write_rendered_output_review_image(path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 500), "white")
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("DejaVuSans.ttf", 34)
        body_font = ImageFont.truetype("DejaVuSans.ttf", 28)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    draw.rounded_rectangle(
        (25, 25, 875, 475),
        radius=20,
        fill="#eff6ff",
        outline="#2563eb",
        width=4,
    )
    draw.text(
        (60, 60),
        "RENDERED OUTPUT REVIEW",
        fill="#1e3a8a",
        font=title_font,
    )
    instructions = (
        "TITLE: Quarterly Revenue",
        "WIDTH: 720",
        "LABEL ANGLE: -30",
        "SORT: descending revenue",
        "REVIEW CODE: MANGO-47",
    )
    for index, instruction in enumerate(instructions):
        draw.text(
            (75, 145 + index * 58),
            instruction,
            fill="#111827",
            font=body_font,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def _setup_rendered_output_review(root: Path) -> ScenarioWorkspace:
    image = root / "fixtures" / "rendered-output-review.png"
    _write_rendered_output_review_image(image)
    return _workspace(
        root,
        {
            "top_product": "Gamma",
            "total_revenue": 235,
            "review_code": "MANGO-47",
        },
        notebook_source=_RENDERED_OUTPUT_REVIEW_NOTEBOOK,
        required_source_fragments=(
            'title="Quarterly Revenue"',
            "width=720",
            "labelAngle=-30",
            '"review_code": "MANGO-47"',
        ),
        required_source_patterns=(
            (
                r"(?:sort\s*=\s*[\"']-y[\"']|"
                r"sort_values\([\"']revenue[\"'],\s*ascending=False\))"
            ),
        ),
        forbidden_source_fragments=(
            'title="Revenue"',
            "width=300",
            "labelAngle=0",
            '"review_code": "pending"',
        ),
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
            """Analyze `data/products.csv` and `data/orders.csv`. Normalize
category whitespace and case to title case, label missing categories Unknown,
and exclude orders whose unit price is missing. Chart revenue by category. Set
`analysis_summary` with `top_category`, `top_category_revenue`,
`total_valid_revenue`, and `excluded_order_count`.

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


HOLDOUT_SCENARIOS = (
    Scenario(
        id="historical_exact_restore",
        description="Restore exact source inspected before several revisions.",
        length="long",
        failure_modes=(
            "historical_source_recall",
            "requirement_reversal",
            "context_retention",
        ),
        setup=_setup_historical_restore,
        turns=(
            "Inspect the existing notebook carefully so you understand its current metric implementation. Do not edit it and do not explain the implementation yet; just confirm when you are ready.",
            "Replace the current metric with the median of raw_scores and update analysis_summary to identify the method as median.",
            "Without editing, explain when a median is preferable to a bounded mean.",
            "Add a compact table that shows every raw score and whether it is above or below the median. Keep the median headline metric.",
            "Without editing, describe the current notebook dependency flow in one short paragraph.",
            "Restore the metric cell and analysis_summary exactly to the implementation you inspected in the first turn, including its original algorithm, constants, method label, and rounding. Remove the median-only table and imports. Verify the restored result.",
        ),
    ),
    Scenario(
        id="large_reactive_graph_repair",
        description="Repair and extend a 26-cell reactive dependency graph.",
        length="medium",
        failure_modes=(
            "large_notebook_inspection",
            "reactive_dependencies",
            "targeted_edit",
        ),
        setup=_setup_large_reactive_graph,
        turns=(
            "Inspect the existing reactive notebook. One numbered stage uses the wrong increment: every stage N should add N to the preceding value. Repair only that stage, preserve the graph, and verify the final summary.",
            "Extend the existing checkpoints dictionary in place to include stage_24 without defining a second checkpoints variable. Keep analysis_summary unchanged and verify the notebook.",
        ),
    ),
    Scenario(
        id="mixed_editor_capabilities",
        description="Combine package, UI-state, cell-edit, and layout operations.",
        length="medium",
        failure_modes=(
            "package_installation",
            "ui_interaction",
            "cell_configuration",
            "tool_selection",
        ),
        setup=_setup_mixed_capabilities,
        isolated_environment=True,
        turns=(
            "Install packages/eval_scaler-0.1.0-py3-none-any.whl through notebook package management. Update the summary cell to use eval_scaler.scaled_total and include package_name='eval-scaler' in analysis_summary. Preserve the current live UI behavior.",
            "Set the live multiplier control to 4 without changing its source default. Hide the code for load_data, keep controls before load_data, and verify analysis_summary reports the package name, selected multiplier, and scaled total.",
        ),
    ),
    Scenario(
        id="campaign_clarification_long",
        description="Delay implementation through ambiguity and explanation turns.",
        length="long",
        failure_modes=(
            "clarification",
            "non_mutating_turns",
            "context_retention",
            "requirement_revision",
        ),
        setup=_setup_campaign_clarification,
        turns=(
            "Inspect data/campaigns.csv. I want campaign ROAS, but I have not decided whether revenue means booked or collected. Do not edit the notebook until I clarify the revenue basis; tell me what decision you need.",
            "Use collected revenue. Build a reproducible campaign and segment analysis with total spend, total revenue, and ROAS.",
            "Do not edit anything. Briefly explain how booked-revenue ROAS would differ conceptually from collected-revenue ROAS.",
            "Add a segment comparison and identify the segment with the most collected revenue.",
            "Correction: internal campaigns must be excluded from every headline calculation and comparison. Update the analysis in place.",
            "Finish with analysis_summary containing revenue_basis='collected', total_spend, total_revenue, roas rounded to four decimals, and top_segment. Validate the exclusion and totals before finishing.",
        ),
    ),
    Scenario(
        id="live_human_edit",
        description="Respond to a human edit made in the live notebook between turns.",
        length="medium",
        failure_modes=(
            "concurrent_human_edit",
            "stale_conversation_state",
            "reactive_execution",
        ),
        setup=_setup_live_human_edit,
        live_cell_edits=(
            LiveCellEdit(
                before_turn=2,
                cell_name="policy",
                code=_LIVE_POLICY_EDIT,
            ),
        ),
        turns=(
            "Inspect the existing order analysis. Add a region comparison and identify the top region while preserving the current revenue policy.",
            "I edited the policy cell in the live notebook while we were talking. Re-read the live notebook rather than relying on the earlier conversation. Respect my new policy, update downstream analysis in place, and set analysis_summary to revenue_policy, total_revenue, and top_region.",
        ),
    ),
    Scenario(
        id="static_visual_review",
        description="Apply chart corrections communicated only in an attached image.",
        length="short",
        failure_modes=(
            "multimodal_input",
            "visual_instruction_following",
            "chart_editing",
        ),
        setup=_setup_static_visual_review,
        requires_vision=True,
        turns=(
            "The attached design-review image contains the required corrections for the existing chart. Apply every annotated correction to the chart cell, preserve the data and analysis_summary, and verify the notebook.",
        ),
    ),
)


_REVISION_HISTORY_NOTEBOOK = """import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    raw_scores = [3, 18, 27, 42, 88, 130]
    return (raw_scores,)


@app.cell
def _(raw_scores):
    _bounded_scores = [max(12, min(_score, 91)) for _score in raw_scores]
    quality_score = round(sum(_bounded_scores) / len(_bounded_scores), 3)
    analysis_summary = {
        "method": "bounded-12-91",
        "quality_score": quality_score,
    }
    return (analysis_summary, quality_score)


@app.cell
def _(raw_scores):
    audit_rows = [
        {
            "raw_score": _score,
            "within_bounds": 12 <= _score <= 91,
        }
        for _score in raw_scores
    ]
    audit_summary = {
        "outside_bounds": sum(
            not _row["within_bounds"] for _row in audit_rows
        )
    }
    return audit_rows, audit_summary


if __name__ == "__main__":
    app.run()
"""

_REVISION_HISTORY_METRIC_SOURCE = """_bounded_scores = [max(12, min(_score, 91)) for _score in raw_scores]
quality_score = round(sum(_bounded_scores) / len(_bounded_scores), 3)
analysis_summary = {
    "method": "bounded-12-91",
    "quality_score": quality_score,
}"""

_REVISION_HISTORY_AUDIT_SOURCE = """audit_rows = [
    {
        "raw_score": _score,
        "within_bounds": 12 <= _score <= 91,
    }
    for _score in raw_scores
]
audit_summary = {
    "outside_bounds": sum(
        not _row["within_bounds"] for _row in audit_rows
    )
}"""


def _setup_revision_history_restore(root: Path) -> ScenarioWorkspace:
    return _workspace(
        root,
        {"method": "bounded-12-91", "quality_score": 46.333},
        notebook_source=_REVISION_HISTORY_NOTEBOOK,
        required_exact_cell_sources=(
            _REVISION_HISTORY_METRIC_SOURCE,
            _REVISION_HISTORY_AUDIT_SOURCE,
        ),
        forbidden_source_fragments=(
            "statistics.median",
            '"method": "trimmed-one-each"',
        ),
    )


REGRESSION_SCENARIOS = (
    Scenario(
        id="rendered_output_review",
        description=(
            "Read visual-only instructions from a live rendered cell output."
        ),
        length="short",
        failure_modes=(
            "rendered_output_inspection",
            "tool_result_multimodality",
            "visual_instruction_following",
        ),
        setup=_setup_rendered_output_review,
        requires_vision=True,
        turns=(
            (
                "Inspect the live rendered output of the review_card cell. The "
                "instructions are present only in that rendered image; do not "
                "read the fixture file directly. Apply every instruction to "
                "the chart and analysis_summary, preserve the data, and verify "
                "the notebook."
            ),
        ),
    ),
    Scenario(
        id="revision_history_restore",
        description=(
            "Restore the oldest of several cell revisions and a deleted cell."
        ),
        length="long",
        failure_modes=(
            "historical_source_recall",
            "multiple_cell_revisions",
            "deleted_cell_restoration",
            "exact_source_restoration",
        ),
        setup=_setup_revision_history_restore,
        turns=(
            "Inspect the notebook carefully and remember the exact metric and audit implementations. Do not edit anything yet.",
            "Replace the headline metric with the median of raw_scores and update analysis_summary to method='median'. Delete the audit cell.",
            "Change the headline metric again: sort raw_scores, remove one value from each tail, and average the rest. Update analysis_summary to method='trimmed-one-each'. Keep the audit cell deleted.",
            "Without editing the notebook, briefly compare the current trimmed metric with the original bounded metric.",
            "Restore both the original first-turn metric cell and the deleted audit cell exactly from revision history. Remove median- and trimmed-only code, and verify the restored notebook.",
        ),
    ),
)


def _setup_multi_task_marathon(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "orders.csv",
        ["order_id", "region", "revenue", "cost", "is_internal"],
        [
            {
                "order_id": "o1",
                "region": "North",
                "revenue": 120,
                "cost": 70,
                "is_internal": "false",
            },
            {
                "order_id": "o2",
                "region": "South",
                "revenue": 200,
                "cost": 100,
                "is_internal": "false",
            },
            {
                "order_id": "o3",
                "region": "North",
                "revenue": 1000,
                "cost": 10,
                "is_internal": "true",
            },
            {
                "order_id": "o4",
                "region": "West",
                "revenue": 180,
                "cost": 120,
                "is_internal": "false",
            },
            {
                "order_id": "o5",
                "region": "South",
                "revenue": 220,
                "cost": 150,
                "is_internal": "false",
            },
        ],
    )
    _write_csv(
        root / "data" / "returns.csv",
        ["order_id", "refund"],
        [
            {"order_id": "o2", "refund": 20},
            {"order_id": "o4", "refund": 10},
            {"order_id": "o5", "refund": 50},
            {"order_id": "unknown", "refund": 999},
        ],
    )
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
    _write_csv(
        root / "data" / "campaigns.csv",
        ["campaign", "channel", "collected_revenue", "is_internal"],
        [
            {
                "campaign": "c1",
                "channel": "Search",
                "collected_revenue": 300,
                "is_internal": "false",
            },
            {
                "campaign": "c2",
                "channel": "Email",
                "collected_revenue": 250,
                "is_internal": "false",
            },
            {
                "campaign": "c3",
                "channel": "Search",
                "collected_revenue": 900,
                "is_internal": "true",
            },
            {
                "campaign": "c4",
                "channel": "Partner",
                "collected_revenue": 500,
                "is_internal": "false",
            },
        ],
    )
    return _workspace(
        root,
        {
            "net_external_revenue": 640,
            "top_region": "South",
            "breach_count": 3,
            "worst_team": "Core",
            "top_channel": "Partner",
            "ignored_return_count": 1,
        },
        required_source_fragments=(
            "net_external_revenue",
            "breach_count",
            "top_channel",
        ),
    )


def _setup_recall_marathon(root: Path) -> ScenarioWorkspace:
    _write_csv(
        root / "data" / "regions.csv",
        ["region", "sales", "is_internal"],
        [
            {"region": "North", "sales": 120, "is_internal": "false"},
            {"region": "South", "sales": 190, "is_internal": "false"},
            {"region": "West", "sales": 800, "is_internal": "true"},
        ],
    )
    return _workspace(
        root,
        {"method": "bounded-12-91", "quality_score": 46.333},
        notebook_source=_REVISION_HISTORY_NOTEBOOK,
        required_source_fragments=("regional_summary",),
        required_exact_cell_sources=(
            _REVISION_HISTORY_METRIC_SOURCE,
            _REVISION_HISTORY_AUDIT_SOURCE,
        ),
        forbidden_source_fragments=(
            "statistics.median",
            '"method": "trimmed-one-each"',
        ),
    )


EXTREME_SCENARIOS = (
    Scenario(
        id="multi_task_marathon",
        description=(
            "Complete several unrelated analyses in one persistent thread."
        ),
        length="long",
        failure_modes=(
            "extreme_conversation_length",
            "task_switching",
            "early_constraint_recall",
            "context_growth",
        ),
        setup=_setup_multi_task_marathon,
        turns=(
            "Inspect all four CSV files in data/. Do not edit yet. For every future task, exclude internal records, count an SLA breach only when resolution_hours is strictly greater than sla_hours, and use collected campaign revenue. Confirm these policies concisely.",
            "Build the external order analysis with gross revenue, cost, margin, and the top region by gross revenue.",
            "Incorporate returns into the order analysis. Ignore return rows whose order_id is absent from the external orders, report that ignored count, and rank regions by net revenue.",
            "Do not edit anything. Briefly explain why the unknown return must not reduce external revenue.",
            "Add a separate support-ticket analysis with breach count and the team with the most breaches. Preserve the order analysis.",
            "Add a separate campaign analysis using the revenue basis I specified at the beginning. Report revenue by channel and the top channel. Preserve the prior analyses.",
            "Add one compact combined KPI table covering orders, support, and campaigns without duplicating the underlying calculations.",
            "Update currency outputs to two decimal places and ensure top_region is based on net, not gross, revenue. Do not change the SLA or campaign policies.",
            "Hide code for the raw-data loading cells and keep the combined KPI presentation after all calculations.",
            "Do not edit the notebook. State the three policies from my first message and say which current calculation enforces each one.",
            "Audit the notebook for duplicated definitions or stale intermediate calculations. Fix only real issues and preserve all requested outputs.",
            "Finish by verifying the notebook and setting analysis_summary to exactly these keys: net_external_revenue, top_region, breach_count, worst_team, top_channel, and ignored_return_count.",
        ),
    ),
    Scenario(
        id="recall_marathon",
        description=(
            "Return to exact early notebook state after several intervening tasks."
        ),
        length="long",
        failure_modes=(
            "extreme_conversation_length",
            "historical_source_recall",
            "task_switching",
            "exact_source_restoration",
        ),
        setup=_setup_recall_marathon,
        turns=(
            "Inspect the notebook carefully and remember the exact metric and audit implementations. Do not edit anything yet.",
            "Replace the headline metric with the median of raw_scores, set method='median', and delete the audit cell.",
            "Now work on a separate task: analyze data/regions.csv, exclude internal rows, and add regional_summary with total_sales and top_region. Preserve the current metric.",
            "Add a compact regional sales table. Do not alter the metric task.",
            "Change the headline metric again: sort raw_scores, remove one value from each tail, average the rest, and set method='trimmed-one-each'.",
            "Without editing, compare the current trimmed metric with the original bounded metric and explain the tradeoff briefly.",
            "Re-check the regional analysis against the source CSV and correct it only if internal rows are included.",
            "Hide code for the regional data-loading cell and keep its table after the regional calculation.",
            "Do not edit. State the original clamp bounds, method label, and rounding precision from the first turn.",
            "Restore the original metric cell and deleted audit cell exactly from revision history. Keep the regional analysis, remove median- and trimmed-only code, and verify everything.",
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
    suite: Literal[
        "quick",
        "full",
        "capabilities",
        "holdout",
        "regression",
        "extreme",
        "all",
    ] = "full",
) -> tuple[Scenario, ...]:
    all_scenarios = (
        *SCENARIOS,
        *CAPABILITY_SCENARIOS,
        *HOLDOUT_SCENARIOS,
        *REGRESSION_SCENARIOS,
        *EXTREME_SCENARIOS,
    )
    selected_ids = ids
    if selected_ids is None and suite == "quick":
        selected_ids = _QUICK_SCENARIO_IDS
    if selected_ids is None and suite == "full":
        return SCENARIOS
    if selected_ids is None and suite == "capabilities":
        return CAPABILITY_SCENARIOS
    if selected_ids is None and suite == "holdout":
        return HOLDOUT_SCENARIOS
    if selected_ids is None and suite == "regression":
        return REGRESSION_SCENARIOS
    if selected_ids is None and suite == "extreme":
        return EXTREME_SCENARIOS
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
