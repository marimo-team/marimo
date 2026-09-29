# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

import pytest
from inline_snapshot import snapshot

from marimo._template_catalog.catalog import (
    CatalogValidationError,
    TemplateCatalog,
    TemplateNotFoundError,
    load_default_catalog,
)

if TYPE_CHECKING:
    from pathlib import Path


def _category(category_id: str) -> dict[str, Any]:
    return {
        "id": category_id,
        "title": "Examples",
        "description": "Small examples.",
    }


def _template(
    template_id: str,
    *,
    notebook: str = "notebooks/example.py",
    categories: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": template_id,
        "notebook": notebook,
        "title": "Example",
        "description": "A small example.",
        "categories": categories or ["examples"],
    }


def _manifest() -> dict[str, Any]:
    return {
        "categories": [_category("examples")],
        "featured": ["example"],
        "templates": [_template("example")],
    }


def test_default_catalog() -> None:
    catalog = load_default_catalog()

    assert {
        "categories": [asdict(category) for category in catalog.categories],
        "entries": [
            {
                **asdict(entry),
                "notebook_path": entry.notebook_path.name,
                "preview_path": entry.preview_path.name,
            }
            for entry in catalog.entries
        ],
        "featured_ids": catalog.featured_ids,
    } == snapshot(
        {
            "categories": [
                {
                    "id": "data-analysis",
                    "title": "Data analysis",
                    "description": "Load, filter, query, and clean data.",
                },
                {
                    "id": "visualization",
                    "title": "Visualization",
                    "description": "Create interactive charts and dashboards.",
                },
                {
                    "id": "apps-and-reports",
                    "title": "Apps and reports",
                    "description": "Build useful tools, forms, and reusable reports.",
                },
            ],
            "entries": [
                {
                    "id": "load-csv",
                    "title": "Explore a CSV",
                    "description": "Upload a CSV or start with sample rows, then inspect it in a table.",
                    "category_ids": ("data-analysis",),
                    "notebook_path": "load_csv.py",
                    "preview_path": "load-csv.png",
                },
                {
                    "id": "filter-data",
                    "title": "Filter and summarize data",
                    "description": "Filter sample sales and summarize the rows you select.",
                    "category_ids": ("data-analysis",),
                    "notebook_path": "filter_data.py",
                    "preview_path": "filter-data.png",
                },
                {
                    "id": "query-with-duckdb",
                    "title": "Query data with SQL",
                    "description": "Start with sample sales and an editable DuckDB query.",
                    "category_ids": ("data-analysis",),
                    "notebook_path": "query_with_duckdb.py",
                    "preview_path": "query-with-duckdb.png",
                },
                {
                    "id": "data-explorer",
                    "title": "Create an interactive chart",
                    "description": "Explore fuel economy with filters, tooltips, and zoom.",
                    "category_ids": ("visualization",),
                    "notebook_path": "data_explorer.py",
                    "preview_path": "data-explorer.png",
                },
                {
                    "id": "dashboard",
                    "title": "Build a dashboard",
                    "description": "Combine a filter, key metrics, a chart, and a detail table.",
                    "category_ids": ("visualization",),
                    "notebook_path": "dashboard.py",
                    "preview_path": "dashboard.png",
                },
                {
                    "id": "interactive-controls",
                    "title": "Build a calculator",
                    "description": "Estimate a monthly budget from a few assumptions.",
                    "category_ids": ("apps-and-reports",),
                    "notebook_path": "interactive_controls.py",
                    "preview_path": "interactive-controls.png",
                },
                {
                    "id": "clean-data",
                    "title": "Clean and transform data",
                    "description": "Fill missing values and calculate derived columns with Polars.",
                    "category_ids": ("data-analysis",),
                    "notebook_path": "clean_data.py",
                    "preview_path": "clean-data.png",
                },
                {
                    "id": "data-entry-form",
                    "title": "Create a data-entry form",
                    "description": "Collect related inputs and turn them into a structured record.",
                    "category_ids": ("apps-and-reports",),
                    "notebook_path": "data_entry_form.py",
                    "preview_path": "data-entry-form.png",
                },
                {
                    "id": "parameterized-report",
                    "title": "Create a parameterized report",
                    "description": "Generate a reusable status report from a few parameters.",
                    "category_ids": ("apps-and-reports",),
                    "notebook_path": "parameterized_report.py",
                    "preview_path": "parameterized-report.png",
                },
            ],
            "featured_ids": (
                "load-csv",
                "filter-data",
                "query-with-duckdb",
                "data-explorer",
                "dashboard",
                "interactive-controls",
            ),
        }
    )


def test_get_unknown_template() -> None:
    with pytest.raises(TemplateNotFoundError, match="missing"):
        load_default_catalog().get("missing")


def test_uses_catalog_preview(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["templates"][0]["preview"] = "previews/example.png"
    _write_catalog(tmp_path, manifest)
    previews = tmp_path / "previews"
    previews.mkdir()
    expected = previews / "example.png"
    expected.write_bytes(b"preview")

    catalog = TemplateCatalog.from_directory(tmp_path)

    assert catalog.get("example").preview_path == expected


@pytest.mark.parametrize(
    ("update", "message"),
    [
        (
            {"categories": []},
            "must define at least one category",
        ),
        (
            {
                "categories": [
                    _category("examples"),
                    _category("examples"),
                ]
            },
            "Duplicate category IDs: examples",
        ),
        (
            {"featured": ["missing"]},
            "Featured template IDs are not in the catalog: missing",
        ),
        (
            {
                "templates": [
                    _template("example"),
                    _template("example"),
                ]
            },
            "Duplicate template IDs: example",
        ),
        (
            {"templates": [_template("Bad ID")]},
            "Invalid template ID 'Bad ID'",
        ),
        (
            {"templates": [_template("example", categories=["missing"])]},
            "uses unknown categories: missing",
        ),
        (
            {"templates": [_template("example", notebook="../outside.py")]},
            "notebook must stay inside the catalog",
        ),
        (
            {
                "templates": [
                    _template("example", notebook="notebooks/missing.py")
                ]
            },
            "notebook does not exist",
        ),
    ],
)
def test_invalid_catalog(
    tmp_path: Path,
    update: dict[str, Any],
    message: str,
) -> None:
    manifest = _manifest()
    manifest.update(update)
    _write_catalog(tmp_path, manifest)

    with pytest.raises(CatalogValidationError, match=message):
        TemplateCatalog.from_directory(tmp_path)


def test_rejects_script_metadata(tmp_path: Path) -> None:
    _write_catalog(tmp_path, _manifest())
    notebook = tmp_path / "notebooks" / "example.py"
    notebook.write_text(
        "# /// script\n# dependencies = []\n# ///\n" + _notebook_source(),
        encoding="utf-8",
    )

    with pytest.raises(
        CatalogValidationError,
        match="must not contain PEP 723 metadata",
    ):
        TemplateCatalog.from_directory(tmp_path)


def test_rejects_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "catalog.json").write_text("not-json", encoding="utf-8")

    with pytest.raises(CatalogValidationError, match="Cannot read"):
        TemplateCatalog.from_directory(tmp_path)


def _write_catalog(root: Path, manifest: dict[str, Any]) -> None:
    notebooks = root / "notebooks"
    notebooks.mkdir()
    (notebooks / "example.py").write_text(_notebook_source(), encoding="utf-8")
    (root / "catalog.json").write_text(json.dumps(manifest), encoding="utf-8")


def _notebook_source() -> str:
    return """import marimo
app = marimo.App()

@app.cell
def _():
    value = 1
    return (value,)

if __name__ == "__main__":
    app.run()
"""
