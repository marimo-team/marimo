# Copyright 2026 Marimo. All rights reserved.
"""Benchmarks for markdown rendering and markdown notebooks.

`mo.md` is the single most used output primitive in marimo notebooks, and the
markdown notebook format is parsed and serialized on every open and save.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._convert.converters import MarimoConvert
from marimo._output.md import md

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture

SHORT_MARKDOWN = "Hello, **world**! Here is some `inline code`."

RICH_MARKDOWN = r"""
# Heading

A paragraph with **bold**, *italic*, `inline code`, a [link](https://marimo.io)
and a footnote-ish aside.

| column | description        |
| ------ | ------------------ |
| a      | the first column   |
| b      | the second column  |

- bullet one
- bullet two
    - nested bullet
1. numbered one
2. numbered two

> A block quote spanning
> multiple lines.

```python
def f(x: int) -> int:
    return x + 1
```

$$
\int_0^1 x^2 \, dx = \frac{1}{3}
$$

/// admonition | A callout
    type: note

With some body text.
///
"""


def test_md_short(benchmark: BenchmarkFixture) -> None:
    benchmark(md, SHORT_MARKDOWN)


def test_md_rich(benchmark: BenchmarkFixture) -> None:
    benchmark(md, RICH_MARKDOWN)


def test_markdown_to_ir(
    benchmark: BenchmarkFixture, markdown_notebook: str
) -> None:
    """Parse a markdown-flavored notebook into marimo's IR."""

    @benchmark
    def _() -> None:
        MarimoConvert.from_md(markdown_notebook).to_ir()


def test_ir_to_markdown(benchmark: BenchmarkFixture, notebook: str) -> None:
    """Export a notebook to the markdown format."""
    intermediate = MarimoConvert.from_py(notebook)
    benchmark(intermediate.to_markdown)
