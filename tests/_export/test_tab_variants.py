# Copyright 2026 Marimo. All rights reserved.
"""Tests for static-export pre-rendering of `mo.ui.tabs` variants (#6076)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from marimo._export._tab_variants import (
    apply_tab_variants_to_view,
    compute_tab_variant_combos,
    find_tabs_elements,
)
from marimo._export.file import export_html
from marimo._export.requests import (
    HTMLExportOptions,
    HTMLFileExportRequest,
    NotebookExecutionOptions,
)
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.notification import CellNotification
from marimo._session.state.session_view import SessionView
from marimo._utils.marimo_path import MarimoPath


def _session_cells(html: str) -> list[dict[str, Any]]:
    """Extract the exported session's cells from the mount config JSON."""
    import re

    match = re.search(r'\{\s*"filename":', html)
    assert match is not None, "mount config not found in exported HTML"
    config, _ = json.JSONDecoder().raw_decode(html[match.start() :])
    return config["session"]["cells"]


def _cell_outputs_html(cells: list[dict[str, Any]]) -> list[str]:
    outputs = []
    for cell in cells:
        for output in cell["outputs"]:
            data = output["data"]
            if isinstance(data, dict):
                outputs.extend(
                    value for value in data.values() if isinstance(value, str)
                )
    return outputs


if TYPE_CHECKING:
    from pathlib import Path

# Minimal shell satisfying static_notebook_template's placeholders.
_MINIMAL_HTML = """<html><head><title>{{ title }}</title></head>
<body>{{ base_url }}{{ filename }}'{{ mount_config }}'</body></html>"""

_TABS_NOTEBOOK = """import marimo

__generated_with = "0.25.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    tabs = mo.ui.tabs(
        {"Tab A": mo.md("content A"), "Tab B": mo.md("content B")}
    )
    tabs
    return (tabs,)


@app.cell
def _(mo, tabs):
    mo.md(f"selected: {tabs.value}")
    return


if __name__ == "__main__":
    app.run()
"""

_NO_DEPENDENTS_NOTEBOOK = """import marimo

__generated_with = "0.25.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    tabs = mo.ui.tabs(
        {"Tab A": mo.md("content A"), "Tab B": mo.md("content B")}
    )
    tabs
    return (tabs,)


if __name__ == "__main__":
    app.run()
"""


def _write_notebook(tmp_path: Path, contents: str) -> Path:
    notebook = tmp_path / "notebook.py"
    notebook.write_text(contents)
    return notebook


def _tabs_session_view() -> SessionView:
    view = SessionView()
    view.cell_notifications["abcd"] = CellNotification(
        cell_id="abcd",
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data=(
                "<marimo-ui-element object-id='abcd-0'>"
                "<marimo-tabs data-initial-value='&quot;0&quot;' "
                "data-tabs='[&quot;A&quot;,&quot;B&quot;]' "
                "data-orientation='&quot;horizontal&quot;'>"
                "<div data-kind='tab'>content A</div>"
                "<div data-kind='tab'>content B</div>"
                "</marimo-tabs></marimo-ui-element>"
            ),
        ),
        console=[],
        timestamp=0,
    )
    return view


def test_find_tabs_elements_detects_tabs() -> None:
    elements = find_tabs_elements(_tabs_session_view(), cell_ids=["abcd"])
    assert len(elements) == 1
    element = elements[0]
    assert element.object_id == "abcd-0"
    assert element.cell_id == "abcd"
    assert element.num_tabs == 2
    assert element.initial_index == 0


def test_find_tabs_elements_ignores_random_ids() -> None:
    view = SessionView()
    view.cell_notifications["abcd"] = CellNotification(
        cell_id="abcd",
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data=(
                "<marimo-ui-element object-id='some-random-uuid'>"
                "<marimo-tabs data-initial-value='&quot;0&quot;'>"
                "<div data-kind='tab'>content A</div>"
                "</marimo-tabs></marimo-ui-element>"
            ),
        ),
        console=[],
        timestamp=0,
    )
    assert find_tabs_elements(view, cell_ids=["abcd"]) == []


def test_compute_tab_variant_combos() -> None:
    elements = find_tabs_elements(_tabs_session_view(), cell_ids=["abcd"])
    combos = compute_tab_variant_combos(elements)
    # Only the non-default tab value produces an extra run.
    assert combos == [{elements[0].object_id: "1"}]


def test_apply_tab_variants_to_view_wraps_outputs() -> None:
    view = _tabs_session_view()
    view.cell_notifications["efgh"] = CellNotification(
        cell_id="efgh",
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data="<p>selected: Tab A</p>",
        ),
        console=[],
        timestamp=0,
    )
    wrapped = apply_tab_variants_to_view(
        view,
        affected={
            "efgh": {
                "abcd-0:0": {"text/html": "<p>selected: Tab A</p>"},
                "abcd-0:1": {"text/html": "<p>selected: Tab B</p>"},
            }
        },
        default_combo="abcd-0:0",
    )
    assert wrapped is True
    data = view.cell_notifications["efgh"].output.data
    assert isinstance(data, str)
    assert "data-marimo-tab-variants" in data
    assert 'data-tab-combo="abcd-0:0"' in data
    assert 'data-tab-combo="abcd-0:1"' in data
    assert "<p>selected: Tab B</p>" in data
    # The default variant is visible; others are hidden.
    assert data.count("hidden") == 1


async def test_export_html_pre_renders_tab_variants(
    tmp_path: Path, monkeypatch: object
) -> None:
    """End to end: a notebook with tab-dependent cells exports every
    tab's rendering plus the toggle wiring (#6076)."""
    notebook = _write_notebook(tmp_path, _TABS_NOTEBOOK)
    monkeypatch.setattr(
        "marimo._export.exporter.get_html_contents",
        lambda: _MINIMAL_HTML,
    )
    result = await export_html(
        HTMLFileExportRequest(
            path=MarimoPath(notebook),
            options=HTMLExportOptions(files=(), include_code=False),
            execution=NotebookExecutionOptions(cli_args={}, argv=None),
        )
    )
    assert not result.did_error
    html = result.text
    outputs = _cell_outputs_html(_session_cells(html))
    assert outputs, "expected cell outputs in the exported session"
    # The tab options themselves are rendered ...
    assert any("<marimo-tabs" in output for output in outputs)
    # ... and every tab value's downstream rendering is embedded ...
    assert any("data-marimo-tab-variants" in output for output in outputs)
    assert any("selected: Tab B" in output for output in outputs)
    # ... with the wiring that swaps them on tab change.
    assert "marimo-value-input" in html


async def test_export_html_skips_variants_without_dependents(
    tmp_path: Path, monkeypatch: object
) -> None:
    """No downstream cells depend on the tabs: export stays a single run."""
    notebook = _write_notebook(tmp_path, _NO_DEPENDENTS_NOTEBOOK)
    monkeypatch.setattr(
        "marimo._export.exporter.get_html_contents",
        lambda: _MINIMAL_HTML,
    )
    result = await export_html(
        HTMLFileExportRequest(
            path=MarimoPath(notebook),
            options=HTMLExportOptions(files=(), include_code=False),
            execution=NotebookExecutionOptions(cli_args={}, argv=None),
        )
    )
    assert not result.did_error
    html = result.text
    outputs = _cell_outputs_html(_session_cells(html))
    assert any("<marimo-tabs" in output for output in outputs)
    assert not any("data-marimo-tab-variants" in output for output in outputs)
    assert "marimo-value-input" not in html
