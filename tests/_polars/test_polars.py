import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.hypertext import Html

HAS_DEPS = DependencyManager.polars.has()


@pytest.fixture
def simple_lf():
    import polars as pl

    return (
        pl.LazyFrame(
            {
                "a": [1, 2, 3],
                "b": [4, 5, 6],
            }
        )
        .filter(pl.col("a") > 1)
        .group_by("a")
        .agg(pl.col("b").sum())
    )


@pytest.mark.skipif(not HAS_DEPS, reason="polars is required")
def test_show_graph(simple_lf):
    lf = simple_lf

    assert type(lf.mo.show_graph()) is Html
    assert type(lf.mo.show_graph(raw_output=True)) is str


@pytest.mark.skipif(not HAS_DEPS, reason="polars is required")
def test_dot_to_html(simple_lf):
    lf = simple_lf

    dot = lf.show_graph(raw_output=True)

    assert type(lf.mo._dot_to_mermaid_html(dot)) is Html


@pytest.mark.skipif(not HAS_DEPS, reason="polars is required")
def test_parse_node_label(simple_lf):
    lf = simple_lf

    assert lf.mo._parse_node_label(r"\"") == "#quot;"
    assert lf.mo._parse_node_label(r"\n") == "\n"
    assert lf.mo._parse_node_label(r"\"\n\"") == "#quot;\n#quot;"


@pytest.mark.skipif(not HAS_DEPS, reason="polars is required")
def test_dot_to_mermaid(simple_lf):
    lf = simple_lf
    dot = lf.show_graph(raw_output=True)

    mermaid_str = lf.mo._polars_dot_to_mermaid(dot)

    assert type(mermaid_str) is str
    assert mermaid_str == (
        """graph TD
	p2["TABLE
π 2/2;
σ [(col(#quot;a#quot;)) > (1)]"]
	p1["AGG [col(#quot;b#quot;).sum()]
BY
[col(#quot;a#quot;)]"]
	p1 --- p2"""
    )
