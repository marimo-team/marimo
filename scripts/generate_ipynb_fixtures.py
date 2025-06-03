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

    (FIXTURES_DIR / f"{name}.ipynb").write_text(
        jupytext.writes(nb.new_notebook(cells=cells), fmt="ipynb")
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
        "multiple_definitions_scope",
        [
            """K = 2\n
def foo():
    K
    K = 1\
""",
            "K = 1",
        ],
    )
    create_notebook_fixture(
        "multiple_definitions_when_not_encapsulated",
        [
            "x = 1",
            "print(x) # print",
            "x = 2",
            "print(x) # print",
        ],
    )
    create_notebook_fixture(
        "adds_marimo_import_for_momd",
        [
            "mo.md('# Hello')",
            "print('World')",
        ],
    )
    create_notebook_fixture(
        "adds_marimo_import_for_mosql",
        [
            "mo.sql('SELECT * FROM table')",
            "print('World')",
        ],
    )
    create_notebook_fixture(
        "keeps_existing_marimo_import",
        [
            "mo.sql('SELECT * FROM table')",
            "print('World')",
            "import marimo as mo",
        ],
    )
    create_notebook_fixture(
        "keeps_import_order_for_marimo_import",
        [
            "import antigravity; import marimo as mo",
            "mo.md('# Hello')",
        ],
    )
    create_notebook_fixture(
        "keeps_existing_top_level_marimo_import",
        [
            "import marimo as mo",
            "mo.md('# Hello')",
            "print('World')",
        ],
    )
    create_notebook_fixture(
        "adds_marimo_import_if_commented_out",
        [
            "mo.md('# Hello')",
            "# import marimo as mo",
        ],
    )
    create_notebook_fixture(
        "adds_marimo_import_if_within_definition",
        [
            "mo.md('# Hello')",
            "def foo():\n    import marimo as mo",
        ],
    )
    create_notebook_fixture(
        "magic_commands",
        [
            "%%sql\nSELECT * FROM table",
            "%%sql\nSELECT * \nFROM table",
            "%cd /path/to/dir",
            "%mkdir /path/to/dir",
            "%matplotlib inline",
            "\n".join(
                [
                    "%matplotlib inline",
                    "import numpy as np",
                    "import matplotlib.pyplot as plt"
                    "plt.style.use('seaborn-whitegrid')",
                ]
            ),
            "\n".join(
                [
                    "%matplotlib inline foo",
                    "import numpy as np",
                    "import matplotlib.pyplot as pl",
                    "plt.style.use('seaborn-whitegrid')",
                ]
            ),
        ],
    )
    create_notebook_fixture(
        "shell_commands",
        [
            "!pip install package",
            "!ls -l",
        ],
    )
    create_notebook_fixture(
        "duplicate_definitions",
        [
            "a = 1",
            "print(a)",
            "a = 2",
            "print(a)",
            "print(a)",
            "a = 3",
        ],
    )
    create_notebook_fixture(
        "cell_metadata",
        [
            nb.new_code_cell(
                "print('Hello')", metadata={"tags": ["tag1", "tag2"]}
            ),
            "print('World')",
            nb.new_code_cell(
                "print('Hello')", metadata={"tags": ["hide-cell"]}
            ),
        ],
    )
    create_notebook_fixture(
        "removes_duplicate_imports",
        [
            # multi-line
            "import numpy as np\nimport pandas as pd\nimport numpy as np",
            "from sklearn.model_selection import train_test_split\nfrom sklearn.model_selection import cross_val_score",
            "import matplotlib.pyplot as plt\nimport numpy as np",
            # single line
            "import polars as pl",
            "import polars as pl",
        ],
    )
    create_notebook_fixture(
        "fake_marimo_imports",
        [
            "# mo.md('# Hello')",
            "print('mo.sql is not a real call')",
            "mo = 'not the real mo'",
        ],
    )
    create_notebook_fixture(
        "complex_multiple_definitions",
        [
            "x = 1\ny = 2\nprint(x, y)",
            "x = 3\nz = 4\nprint(x, z)",
            "y = 5\nprint(y)",
            "def func():\n    x = 1\n    return x\nfunc()",
            "def func():\n    y = 1\n    return y\nfunc()",
            "xx = 2\nprint(xx)",
            "def another_func():\n    xx = 3\n    return xx",
        ],
    )


if __name__ == "__main__":
    main()
