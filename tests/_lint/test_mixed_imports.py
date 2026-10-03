# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._ast.names import SETUP_CELL_NAME
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    NotebookSerializationV1,
)
from tests._lint.utils import lint_notebook


def notebook_with_cell(code: str, name: str = "_"):
    return NotebookSerializationV1(
        app=AppInstantiation(),
        cells=[CellDef(code=code, name=name, lineno=10, col_offset=4)],
        filename="notebook.py",
    )


@pytest.mark.parametrize(
    ("code", "line"),
    [
        ("import math\nLIMIT = 10", 11),
        ("import math\nimport os\nLIMIT = -10", 12),
        ("from math import sqrt\nLIMIT = 0.5", 11),
        ("import math as m\nLIMIT: int = 10", 11),
        ("import math\nFIRST = SECOND = None", 11),
        ("LIMIT = True\nimport math", 10),
        ("import math\n# configuration\nLIMIT = 10\nLABEL = 'limit'", 12),
        ("import math\nVALUES = [1, -2, 3]\nOPTIONS = {'a': (1, 2)}", 11),
    ],
)
def test_flags_literal_configuration_with_imports(code: str, line: int):
    diagnostics = [
        d for d in lint_notebook(notebook_with_cell(code)) if d.code == "MR005"
    ]
    assert diagnostics == [
        Diagnostic(
            message="Mixing imports with configuration disables incremental imports.",
            line=line,
            column=5,
            code="MR005",
            name="mixed-imports",
            severity=Severity.RUNTIME,
            fixable=False,
            fix=(
                "Move the configuration assignments into a separate cell. "
                "Adding imports to an import-only cell does not rerun "
                "cells that depend on unchanged imports."
            ),
            filename="notebook.py",
        )
    ]


@pytest.mark.parametrize(
    "code",
    [
        "",
        "# comment",
        "import math\nfrom os import path",
        "LIMIT = 10",
        "import math\nLIMIT = math.pi",
        "import math\nLIMIT = int('10')",
        "import math\nLIMIT = set()",
        "import math\nLIMIT = other_limit",
        "import math\nprint('ready')\nLIMIT = 10",
        "import math\ndef compute():\n    return 10",
        "def compute():\n    import math\n    limit = 10",
        "if enabled:\n    import math\n    LIMIT = 10",
        "try:\n    import math\nexcept ImportError:\n    pass\nLIMIT = 10",
        "import math\nmath = 10",
        "import math\nmath.limit = 10",
        "import math\nlimits[0] = 10",
        "from typing import Final\nLIMIT: Final = 10",
        "import math\nLIMIT: int",
        "import math as _math\nLIMIT = 10",
        "from math import *\nLIMIT = 10",
        "from __future__ import annotations\nLIMIT = 10",
        "import math\nLIMIT =",
    ],
)
def test_does_not_flag_other_cell_patterns(code: str):
    assert [
        d for d in lint_notebook(notebook_with_cell(code)) if d.code == "MR005"
    ] == []


def test_does_not_flag_setup_cell():
    notebook = notebook_with_cell("import math\nLIMIT = 10", SETUP_CELL_NAME)
    assert [d for d in lint_notebook(notebook) if d.code == "MR005"] == []


def test_can_ignore_mixed_imports():
    notebook = notebook_with_cell("import math\nLIMIT = 10")
    assert [
        d
        for d in lint_notebook(notebook, lint_config={"ignore": ["MR005"]})
        if d.code == "MR005"
    ] == []
