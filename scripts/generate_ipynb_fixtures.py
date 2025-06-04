# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "jupytext",
#     "nbformat",
# ]
#
# [tool.uv]
# exclude-newer = "2025-06-03T16:30:20.082913-04:00"
# ///
"""
Generate `.ipynb` test fixtures for marimo's notebook conversion pipeline.

Each fixture corresponds to a named Jupyter notebook containing one or more code cells.
To add a new fixture, call `create_notebook_fixture(name, sources)`:

- `name`: the output filename (without `.ipynb`)
- `sources`: a list of code cell contents (as strings or `nbformat` cell dicts)

Run this script with `uv run scripts/generate_ipynb_fixtures.py` to regenerate all fixtures.
Output notebooks are written to `tests/_convert/ipynb_data/`.
"""

from __future__ import annotations
from pathlib import Path

import nbformat.v4.nbbase as nb
import jupytext


SELF_DIR = Path(__file__).parent
FIXTURES_DIR = SELF_DIR / "../tests/_convert/ipynb_data"


def create_notebook_fixture(name: str, sources: list[str | dict]) -> None:
    cells = []
    for source in sources:
        if isinstance(source, str):
            cell = nb.new_code_cell(source)
        else:
            cell = source
        cells.append(cell)

    notebook = nb.new_notebook(cells=cells)

    for i, cell in enumerate(notebook.cells):
        cell.id = str(i)  # ensure we always have 1,2,3,4

    (FIXTURES_DIR / f"{name}.ipynb").write_text(
        jupytext.writes(notebook, fmt="ipynb")
    )


def main() -> None:
    FIXTURES_DIR.mkdir(exist_ok=True)
    create_notebook_fixture(
        "multiple_definitions",
        [
            "x = 1\nprint(x) # print",
            "x = 2\nprint(x) # print",
        ],
    )
    create_notebook_fixture(
        "multiple_definitions_multiline",
        [
            "K = 2\nnearest_partition = np.argpartition(dist_sq_1, K + 1, axis=1)",
            """plt.scatter(X_1[:, 0], X_1[:, 1], s=100)
K = 2
for i_1 in range(X_1.shape[0]):
    for j in nearest_partition[i_1, :K + 1]:
        plt.plot(*zip(X_1[j], X_1[i_1]), color='black')\
""",
        ],
    )

    create_notebook_fixture(
        "duplicate_definitions_and_aug_assign",
        [
            "x = 1",
            "x",
            "x += 1",
            "x",
        ],
    )

    create_notebook_fixture(
        "duplicate_definitions_read_before_write",
        [
            "x = 1",
            "x",
            "x; x = 2; x",
            "x",
        ],
    )

    create_notebook_fixture(
        "duplicate_definitions_syntax_error",
        [
            "x ( b 2 d & !",
            "x",
        ],
    )

    create_notebook_fixture(
        "cell_metadata",
        [
            nb.new_code_cell(
                "print('Hello')", metadata={"tags": ["tag1", "tag2"]}
            ),
            nb.new_code_cell("print('World')", metadata={}),
            nb.new_code_cell(
                "print('Cell 1')",
                metadata={"tags": ["important", "data-processing"]},
            ),
            nb.new_code_cell("print('Cell 2')", metadata={"tags": []}),
            nb.new_code_cell(
                "print('Cell 3')",
                metadata={"tags": ["visualization"], "collapsed": True},
            ),
            nb.new_code_cell(
                "print('Complex metadata')",
                metadata={
                    "tags": ["tag1", "tag2"],
                    "collapsed": True,
                    "scrolled": False,
                    "custom": {"key": "value"},
                },
            ),
            nb.new_code_cell(
                "print('hidden cell')",
                metadata={
                    "tags": ["hide-cell"],
                },
            ),
            nb.new_code_cell(
                "print('hidden cell, with other tags')",
                metadata={
                    "tags": ["hide-cell", "remove-print"],
                },
            ),
        ],
    )


if __name__ == "__main__":
    main()
