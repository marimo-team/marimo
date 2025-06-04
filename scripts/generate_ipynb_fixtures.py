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
from io import FileIO
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


if __name__ == "__main__":
    main()
