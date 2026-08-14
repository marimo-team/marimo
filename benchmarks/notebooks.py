# Copyright 2026 Marimo. All rights reserved.
"""Deterministic notebook generators used as benchmark inputs.

Notebooks are built from a small pool of representative cell shapes (imports,
UI elements, markdown, SQL, function and class definitions, comprehensions).
Cells reference variables defined by earlier cells so the generated notebook
has a realistic dependency graph rather than a flat list of isolated cells.
"""

from __future__ import annotations

CELL_TEMPLATES: list[str] = [
    # Plain assignment with a couple of upstream references.
    """\
value_{i} = ({refs}) * {i}
scaled_{i} = [value_{i} * k for k in range({i} % 17 + 3)]
""",
    # Function definition closing over upstream variables.
    """\
def transform_{i}(items):
    total = {refs}
    out = {{}}
    for index, item in enumerate(items):
        out[index] = (item, total + index)
    return out


result_{i} = transform_{i}(range({i} % 11 + 2))
""",
    # Class definition.
    """\
class Model_{i}:
    scale = {refs}

    def __init__(self, name: str) -> None:
        self.name = name
        self._cache: dict[str, int] = {{}}

    def score(self, other: int) -> int:
        if other not in self._cache:
            self._cache[other] = other * self.scale
        return self._cache[other]


model_{i} = Model_{i}("model-{i}")
""",
    # Markdown cell.
    '''\
mo.md(
    f"""
    ## Section {i}

    The current value is **{{{refs}}}**, computed from the cells above.

    - first bullet for section {i}
    - second bullet for section {i}
    """
)
''',
    # UI element.
    """\
slider_{i} = mo.ui.slider(start=0, stop=100, value={i} % 100, label="knob {i}")
value_{i} = slider_{i}.value + ({refs})
""",
    # Comprehensions and control flow.
    """\
records_{i} = [
    {{"id": index, "weight": index * ({refs})}}
    for index in range({i} % 23 + 5)
    if index % 2 == 0
]
heaviest_{i} = max(records_{i}, key=lambda record: record["weight"], default=None)
""",
    # try/except plus a with-block, to exercise the scoped visitor.
    """\
try:
    with open(f"/tmp/marimo-bench-{i}.txt") as handle_{i}:
        contents_{i} = handle_{i}.read()
except OSError as error_{i}:
    contents_{i} = str(error_{i})
finally:
    checksum_{i} = len(contents_{i}) + ({refs})
""",
]

SQL_TEMPLATE = """\
df_{i} = mo.sql(
    f\"\"\"
    CREATE OR REPLACE TABLE table_{i} AS
    SELECT t.id, t.value, s.label
    FROM schema_a.source_{i} AS t
    JOIN schema_b.labels AS s ON s.id = t.id
    WHERE t.value > {i}
    \"\"\"
)
"""

SETUP_CELL = """\
import marimo as mo

base = 1
"""


def _references(defined: list[str]) -> str:
    """Return an expression referencing up to two previously defined names."""
    if not defined:
        return "base"
    if len(defined) == 1:
        return defined[-1]
    return f"{defined[-1]} + {defined[-2]}"


def generate_cell_codes(n_cells: int) -> list[str]:
    """Generate `n_cells` cell sources with a realistic dependency graph."""
    codes: list[str] = []
    defined: list[str] = []
    for index in range(n_cells):
        refs = _references(defined)
        if index % 9 == 8:
            codes.append(SQL_TEMPLATE.format(i=index))
        else:
            template = CELL_TEMPLATES[index % len(CELL_TEMPLATES)]
            codes.append(template.format(i=index, refs=refs))
        # Cells whose template defines `value_<i>` become dependency targets.
        if index % len(CELL_TEMPLATES) in (0, 4) and index % 9 != 8:
            defined.append(f"value_{index}")
    return codes


def generate_notebook_source(n_cells: int) -> str:
    """Generate the source of a marimo notebook with `n_cells` cells."""
    from marimo._ast.app_config import _AppConfig
    from marimo._ast.cell import CellConfig
    from marimo._ast.codegen import generate_filecontents
    from marimo._ast.names import SETUP_CELL_NAME

    codes = [SETUP_CELL, *generate_cell_codes(n_cells)]
    names = [SETUP_CELL_NAME, *(f"cell_{i}" for i in range(n_cells))]
    configs = [CellConfig() for _ in codes]
    return generate_filecontents(
        codes,
        names,
        configs,
        config=_AppConfig(width="medium"),
    )


def generate_markdown_notebook(n_cells: int) -> str:
    """Generate a markdown-flavored marimo notebook."""
    parts = [
        "---",
        "title: Benchmark notebook",
        "marimo-version: 0.0.0",
        "---",
        "",
    ]
    for index, code in enumerate(generate_cell_codes(n_cells)):
        parts.append(f"## Cell {index}")
        parts.append("")
        parts.append(
            "Some prose describing what the cell below does, with "
            "`inline code`, a [link](https://marimo.io), and *emphasis*."
        )
        parts.append("")
        parts.append("```python {.marimo}")
        parts.append(code.rstrip())
        parts.append("```")
        parts.append("")
    return "\n".join(parts)
