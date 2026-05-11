# Copyright 2026 Marimo. All rights reserved.

from typing import Any, cast

import pytest

from marimo._plugins.stateless.mermaid import mermaid


def test_mo_mermaid_diagram_only() -> None:
    assert (
        mermaid("graph TD\nA --> B").text
        == "<marimo-mermaid data-diagram='&quot;graph TD&#92;nA --&gt; B&quot;'></marimo-mermaid>"
    )


def test_mo_mermaid_theme_and_theme_variables() -> None:
    assert (
        mermaid(
            "graph TD\nA --> B",
            theme="base",
            theme_variables={
                "primaryColor": "#E8EEF5",
                "lineColor": "#475569",
            },
        ).text
        == "<marimo-mermaid data-diagram='&quot;graph TD&#92;nA --&gt; B&quot;' data-theme='&quot;base&quot;' data-theme_variables='{&quot;primaryColor&quot;:&quot;#E8EEF5&quot;,&quot;lineColor&quot;:&quot;#475569&quot;}'></marimo-mermaid>"
    )


def test_mo_mermaid_theme_defaults_to_base_with_theme_variables() -> None:
    assert (
        mermaid(
            "graph TD\nA --> B",
            theme_variables={"primaryColor": "#E8EEF5"},
        ).text
        == "<marimo-mermaid data-diagram='&quot;graph TD&#92;nA --&gt; B&quot;' data-theme='&quot;base&quot;' data-theme_variables='{&quot;primaryColor&quot;:&quot;#E8EEF5&quot;}'></marimo-mermaid>"
    )


def test_mo_mermaid_rejects_theme_variables_with_non_base_theme() -> None:
    with pytest.raises(
        ValueError, match="theme_variables require theme='base'"
    ):
        mermaid(
            "graph TD\nA --> B",
            theme="neutral",
            theme_variables={"primaryColor": "#E8EEF5"},
        )


def test_mo_mermaid_accepts_any_theme_string() -> None:
    assert (
        mermaid("graph TD\nA --> B", theme=cast(Any, "custom-new-theme")).text
        == "<marimo-mermaid data-diagram='&quot;graph TD&#92;nA --&gt; B&quot;' data-theme='&quot;custom-new-theme&quot;'></marimo-mermaid>"
    )
