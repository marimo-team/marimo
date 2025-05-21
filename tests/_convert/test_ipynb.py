from __future__ import annotations

import ast
from textwrap import dedent

import pytest

from marimo._convert.ipynb import (
    _transform_sources,
    transform_add_marimo_import,
    transform_cell_metadata,
    transform_duplicate_definitions,
    transform_exclamation_mark,
    transform_fixup_multiple_definitions,
    transform_magic_commands,
    transform_remove_duplicate_imports,
)


def dd(sources: list[str]) -> list[str]:
    return [dedent(s) for s in sources]


def assert_sources_equal(transformed: list[str], expected: list[str]) -> None:
    expected = dd(expected)
    assert len(transformed) == len(expected)
    try:
        transformed = [ast.unparse(ast.parse(t)) for t in transformed]
    except SyntaxError:
        transformed = [t for t in transformed]
    try:
        expected = [ast.unparse(ast.parse(e)) for e in expected]
    except SyntaxError:
        expected = [e for e in expected]
    assert transformed == expected


def test_transform_fixup_multiple_definitions():
    # Makes everything private to avoid conflicts.
    # Comments are removed, unfortunately.
    sources = [
        "x = 1\nprint(x) # print",
        "x = 2\nprint(x) # print",
    ]
    result = transform_fixup_multiple_definitions(sources)
    assert result == [
        "_x = 1\nprint(_x)",
        "_x = 2\nprint(_x)",
    ]


def test_transform_fixup_multiple_definitions_multiline():
    # Makes everything private to avoid conflicts.
    # Comments are removed, unfortunately.
    sources = dd(
        [
            """K = 2\n
nearest_partition = np.argpartition(dist_sq_1, K + 1, axis=1)
""",
            """
plt.scatter(X_1[:, 0], X_1[:, 1], s=100)
K = 2
for i_1 in range(X_1.shape[0]):
    for j in nearest_partition[i_1, :K + 1]:
        plt.plot(*zip(X_1[j], X_1[i_1]), color='black')
""",
        ]
    )
    result = transform_fixup_multiple_definitions(sources)
    expected = [
        """_K = 2\n
nearest_partition = np.argpartition(dist_sq_1, _K + 1, axis=1)
""",
        """
plt.scatter(X_1[:, 0], X_1[:, 1], s=100)
_K = 2
for i_1 in range(X_1.shape[0]):
    for j in nearest_partition[i_1, :_K + 1]:
        plt.plot(*zip(X_1[j], X_1[i_1]), color='black')
""",
    ]
    assert_sources_equal(result, expected)


def test_transform_fixup_multiple_definitions_scope():
    # Makes everything private to avoid conflicts.
    # Comments are removed, unfortunately.
    sources = dd(
        [
            """K = 2\n
def foo():
    K
    K = 1
""",
            "K = 1",
        ]
    )
    result = transform_fixup_multiple_definitions(sources)
    expected = [
        """_K = 2\n
def foo():
    _K
    _K = 1
""",
        "_K = 1",
    ]

    assert_sources_equal(result, expected)


def test_transform_fixup_multiple_definitions_when_not_encapsulated():
    # Since the definitions are not encapsulated in a single cell, they should
    # not be transformed.
    sources = [
        "x = 1",
        "print(x) # print",
        "x = 2",
        "print(x) # print",
    ]
    result = transform_fixup_multiple_definitions(sources)
    assert result == sources


def test_transform_add_marimo_import():
    # mo.md
    sources = [
        "mo.md('# Hello')",
        "print('World')",
    ]
    result = transform_add_marimo_import(sources)
    assert "import marimo as mo" in result

    # mo.sql
    sources = [
        "mo.sql('SELECT * FROM table')",
        "print('World')",
    ]
    result = transform_add_marimo_import(sources)
    assert "import marimo as mo" in result

    # if `import marimo as mo` is already present
    # it should not be added again
    existing = sources + ["import marimo as mo"]
    assert transform_add_marimo_import(existing) == existing

    existing = [
        # slight support for different import orders
        # but must use canonical "import marimo as mo" form
        "import antigravity; import marimo as mo",
        "mo.md('# Hello')",
    ]
    assert transform_add_marimo_import(existing) == existing


def test_transform_add_marimo_import_already_imported():
    sources = [
        "import marimo as mo",
        "mo.md('# Hello')",
        "print('World')",
    ]
    result = transform_add_marimo_import(sources)
    assert result == sources


def test_transform_add_marimo_import_already_but_in_comment_or_definition():
    # Comment
    sources = [
        "mo.md('# Hello')",
        "# import marimo as mo",
    ]
    result = transform_add_marimo_import(sources)
    assert result == sources + ["import marimo as mo"]

    # Definition
    sources = [
        "mo.md('# Hello')",
        "def foo():\n    import marimo as mo",
    ]
    result = transform_add_marimo_import(sources)
    assert result == sources + ["import marimo as mo"]


def test_transform_magic_commands():
    sources = [
        "%%sql\nSELECT * FROM table",
        "%%sql\nSELECT * \nFROM table",
        "%cd /path/to/dir",
        "%mkdir /path/to/dir",
        "%matplotlib inline",
    ]
    result = transform_magic_commands(sources)
    assert result == [
        '_df = mo.sql("""\nSELECT * FROM table\n""")',
        '_df = mo.sql("""\nSELECT * \nFROM table\n""")',
        "import os\nos.chdir('/path/to/dir')",
        "import os\nos.makedirs('/path/to/dir', exist_ok=True)",
        "# '%matplotlib inline' command supported automatically in marimo",
    ]


def test_transform_magic_command_with_code():
    sources = dd(
        [
            """
        %matplotlib inline
        import numpy as np
        import matplotlib.pyplot as plt
        plt.style.use('seaborn-whitegrid')
        """
        ]
    )
    result = transform_magic_commands(sources)
    expected = dd(
        [
            """# '%matplotlib inline' command supported automatically in marimo
import numpy as np
import matplotlib.pyplot as plt
plt.style.use('seaborn-whitegrid')"""
        ]
    )
    assert result == expected


def test_transform_magic_command_multiple_args_with_code():
    sources = dd(
        [
            """
        %matplotlib inline foo
        import numpy as np
        import matplotlib.pyplot as plt
        plt.style.use('seaborn-whitegrid')
        """
        ]
    )
    result = transform_magic_commands(sources)
    expected = dd(
        [
            """# '%matplotlib inline foo' command supported automatically in marimo
import numpy as np
import matplotlib.pyplot as plt
plt.style.use('seaborn-whitegrid')"""
        ]
    )
    assert result == expected


def test_transform_exclamation_mark():
    sources = [
        "!pip install package",
        "!ls -l",
    ]
    result = transform_exclamation_mark(sources)
    assert result == [
        "# (use marimo's built-in package management features instead) !pip install package",  # noqa: E501
        "!ls -l",
    ]


def test_transform_duplicate_definitions():
    sources = [
        "a = 1",
        "print(a)",
        "a = 2",
        "print(a)",
        "print(a)",
        "a = 3",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "a = 1",
        "print(a)",
        "a_1 = 2",
        "print(a_1)",
        "print(a_1)",
        "a_2 = 3",
    ]


def test_transform_cell_metadata():
    sources = [
        "print('Hello')",
        "print('World')",
    ]
    metadata = [
        {"tags": ["tag1", "tag2"]},
        {},
    ]
    result = transform_cell_metadata(sources, metadata)
    assert result == [
        "# Cell tags: tag1, tag2\nprint('Hello')",
        "print('World')",
    ]


def test_transform_remove_duplicate_imports():
    sources = [
        "import numpy as np\nimport pandas as pd\nimport numpy as np",
        "from sklearn.model_selection import train_test_split\nfrom sklearn.model_selection import cross_val_score",  # noqa: E501
        "import matplotlib.pyplot as plt\nimport numpy as np",
    ]
    result = transform_remove_duplicate_imports(sources)
    assert result == [
        "import numpy as np\nimport pandas as pd",
        "from sklearn.model_selection import train_test_split\nfrom sklearn.model_selection import cross_val_score",  # noqa: E501
        "import matplotlib.pyplot as plt",
    ]


def test_transform_remove_duplicate_imports_single_line():
    sources = [
        "import polars as pl",
        "import polars as pl",
    ]
    result = transform_remove_duplicate_imports(sources)
    assert result == [
        "import polars as pl",
        "",
    ]


def test_transform_fixup_multiple_definitions_complex():
    sources = [
        "x = 1\ny = 2\nprint(x, y)",
        "x = 3\nz = 4\nprint(x, z)",
        "y = 5\nprint(y)",
    ]
    result = transform_fixup_multiple_definitions(sources)
    assert result == [
        "_x = 1\n_y = 2\nprint(_x, _y)",
        "_x = 3\nz = 4\nprint(_x, z)",
        "_y = 5\nprint(_y)",
    ]


def test_transform_fixup_multiple_definitions_with_functions():
    sources = [
        "def func():\n    x = 1\n    return x\nfunc()",
        "def func():\n    y = 1\n    return y\nfunc()",
        "x = 2\nprint(x)",
        "def another_func():\n    x = 3\n    return x",
    ]
    result = transform_fixup_multiple_definitions(sources)
    assert result == [
        "def _func():\n    x = 1\n    return x\n_func()",
        "def _func():\n    y = 1\n    return y\n_func()",
        "x = 2\nprint(x)",
        "def another_func():\n    x = 3\n    return x",
    ]


def test_transform_add_marimo_import_edge_cases():
    sources = [
        "# mo.md('# Hello')",
        "print('mo.sql is not a real call')",
        "mo = 'not the real mo'",
    ]
    result = transform_add_marimo_import(sources)
    assert "import marimo as mo" not in result


def test_transform_magic_commands_complex():
    sources = [
        "%%sql\nSELECT *\nFROM table\nWHERE condition",
        "%%time\nfor i in range(1000000):\n    pass",
        "%load_ext autoreload\n%autoreload 2",
        "%env MY_VAR=value",
    ]
    result = transform_magic_commands(sources)
    expected = [
        '_df = mo.sql("""\nSELECT *\nFROM table\nWHERE condition\n""")',
        (
            "# magic command not supported in marimo; please file an issue to add support\n"  # noqa: E501
            "# %%time\nfor i in range(1000000):\n"
            "    pass"
        ),
        (
            "# magic command not supported in marimo; please file an issue to add support\n"  # noqa: E501
            "# %load_ext autoreload\n"
            "# '%autoreload 2' command supported automatically in marimo"
        ),
        "import os\nos.environ['MY_VAR'] = 'value'",
    ]
    assert result == expected


def test_transform_exclamation_mark_complex():
    sources = [
        "!pip install package1 package2",
        "! ls -l | grep '.py'",
        "result = !echo 'Hello, World!'",
        "!python script.py arg1 arg2",
    ]
    result = transform_exclamation_mark(sources)
    assert result == [
        "# (use marimo's built-in package management features instead) !pip install package1 package2",  # noqa: E501
        # These are currently unhandled.
        "! ls -l | grep '.py'",
        "result = !echo 'Hello, World!'",
        "!python script.py arg1 arg2",
    ]


def test_transform_duplicate_definitions_complex():
    sources = [
        "x = 1 # comment unaffected",
        "a = 1\nb = 2\nprint(a, b)",
        "a = 3\nc = 4\nprint(a, c)",
        "b = 5\nd = 6\nprint(b, d)",
        "a = 7\nb = 8\nc = 9\nprint(a, b, c)",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "x = 1 # comment unaffected",
        "a = 1\nb = 2\nprint(a, b)",
        "a_1 = 3\nc = 4\nprint(a_1, c)",
        "b_1 = 5\nd = 6\nprint(b_1, d)",
        "a_2 = 7\nb_2 = 8\nc_1 = 9\nprint(a_2, b_2, c_1)",
    ]


def test_transform_cell_metadata_complex():
    sources = [
        "print('Cell 1')",
        "print('Cell 2')",
        "print('Cell 3')",
    ]
    metadata = [
        {"tags": ["important", "data-processing"]},
        {"tags": []},
        {"tags": ["visualization"], "collapsed": True},
    ]
    result = transform_cell_metadata(sources, metadata)
    assert result == [
        "# Cell tags: important, data-processing\nprint('Cell 1')",
        "print('Cell 2')",
        "# Cell tags: visualization\nprint('Cell 3')",
    ]


def test_transform_remove_duplicate_imports_complex():
    sources = [
        "import numpy as np\nfrom pandas import DataFrame\nimport matplotlib.pyplot as plt",  # noqa: E501
        "from sklearn.model_selection import train_test_split, cross_val_score\nimport numpy as np",  # noqa: E501
        "from pandas import Series\nfrom matplotlib import pyplot as plt\nimport pandas as pd",  # noqa: E501
    ]
    result = transform_remove_duplicate_imports(sources)
    assert result == [
        "import numpy as np\nfrom pandas import DataFrame\nimport matplotlib.pyplot as plt",  # noqa: E501
        "from sklearn.model_selection import train_test_split, cross_val_score",  # noqa: E501
        "from pandas import Series\nfrom matplotlib import pyplot as plt\nimport pandas as pd",  # noqa: E501
    ]


def test_transform_fixup_multiple_definitions_with_classes():
    sources = [
        "class MyClass:\n    x = 1\n    def method(self):\n        return self.x",  # noqa: E501
        "x = 2\nprint(x)",
        "class MyClass:\n    x = 3\n    def method(self):\n        return self.x",  # noqa: E501
    ]
    result = transform_fixup_multiple_definitions(sources)
    assert result == [
        "class _MyClass:\n    x = 1\n\n    def method(self):\n        return self.x",  # noqa: E501
        "x = 2\nprint(x)",
        "class _MyClass:\n    x = 3\n\n    def method(self):\n        return self.x",  # noqa: E501
    ]


def test_transform_magic_commands_unsupported():
    sources = [
        "%custom_magic arg1 arg2",
        "%%custom_cell_magic\nsome\ncontent",
    ]
    result = transform_magic_commands(sources)
    assert result == [
        "# magic command not supported in marimo; please file an issue to add support\n# %custom_magic arg1 arg2",  # noqa: E501
        "# magic command not supported in marimo; please file an issue to add support\n# %%custom_cell_magic\n# some\n# content",  # noqa: E501
    ]


def test_transform_exclamation_mark_with_variables():
    sources = [
        "package = 'numpy'\n!pip install {package}",
        "command = 'echo \"Hello, World!\"'\n!{command}",
    ]
    result = transform_exclamation_mark(sources)
    assert result == [
        "package = 'numpy'\n# (use marimo's built-in package management features instead) !pip install {package}",  # noqa: E501
        "command = 'echo \"Hello, World!\"'\n!{command}",
    ]


def test_transform_duplicate_definitions_with_comprehensions():
    sources = [
        "[x for x in range(10)]",
        "x = 5\nprint(x)",
        "{x: x**2 for x in range(5)}",
        "x = 10\nprint(x)",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "[x for x in range(10)]",
        "x = 5\nprint(x)",
        "{x: x**2 for x in range(5)}",
        "x_1 = 10\nprint(x_1)",
    ]


def test_transform_duplicate_definitions_with_reference_to_previous():
    sources = [
        "x = 1",
        "x = x + 1\nprint(x)",
        "print(x)",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "x = 1",
        "x_1 = x + 1\nprint(x_1)",
        "print(x_1)",
    ]


def test_transform_cell_metadata_with_complex_metadata():
    sources = [
        "print('Complex metadata')",
    ]
    metadata = [
        {
            "tags": ["tag1", "tag2"],
            "collapsed": True,
            "scrolled": False,
            "custom": {"key": "value"},
        }
    ]
    result = transform_cell_metadata(sources, metadata)
    assert result == [
        "# Cell tags: tag1, tag2\nprint('Complex metadata')",
    ]


def test_transform_remove_duplicate_imports_with_aliases():
    sources = [
        "import numpy as np\nimport pandas as pd",
        "import numpy as numpy\nfrom pandas import DataFrame as DF",
        "import numpy\nfrom pandas import Series",
    ]
    result = transform_remove_duplicate_imports(sources)
    assert result == [
        "import numpy as np\nimport pandas as pd",
        "import numpy as numpy\nfrom pandas import DataFrame as DF",
        "import numpy\nfrom pandas import Series",
    ]


def test_transform_remove_duplicate_imports_single():
    sources = [
        "import polars as pl",
        "import polars as pl",
        "import polars as pl\ndf = pl.DataFrame({'a': [1, 2, 3]})",
    ]
    result = transform_remove_duplicate_imports(sources)
    assert result == [
        "import polars as pl",
        "",
        "df = pl.DataFrame({'a': [1, 2, 3]})",
    ]


# This test currently fails because import deduplication doesn't handle
# multiple imports on one line
@pytest.mark.xfail(
    reason="import deduplication doesn't handle multiple imports on one line"
)
def test_transform_remove_duplicate_imports_with_multiple_on_one_line():
    sources = ["import getpass\nimport os", "import os, import getpass"]

    result = transform_remove_duplicate_imports(sources)
    assert result == [
        "import getpass\nimport os",
        "",
    ]


def test_transform_duplicate_definitions_with_re_def():
    sources = [
        "x = 1",
        "x = x + 1\nprint(x)",
        "x = x + 2\nprint(x)",
        "x = x + 3\nprint(x)",
        "x = 10\nprint(x)",
        "print(x)",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "x = 1",
        "x_1 = x + 1\nprint(x_1)",
        "x_2 = x_1 + 2\nprint(x_2)",
        "x_3 = x_2 + 3\nprint(x_3)",
        "x_4 = 10\nprint(x_4)",
        "print(x_4)",
    ]


def test_transform_duplicate_definitions_with_multiple_variables():
    sources = [
        "x, y = 1, 2",
        "x = x + y\ny = y + x\nprint(x, y)",
        "z = x + y\nx = z\nprint(x, y, z)",
        "x, y, z = y, z, x\nprint(x, y, z)",
    ]
    result = transform_duplicate_definitions(sources)
    assert_sources_equal(
        result,
        dd(
            [
                "x, y = 1, 2",
                "x_1 = x + y\ny_1 = y + x_1\nprint(x_1, y_1)",
                "z = x_1 + y_1\nx_2 = z\nprint(x_2, y_1, z)",
                "x_3, y_2, z_1 = (y_1, z, x_2)\nprint(x_3, y_2, z_1)",
            ]
        ),
    )


def test_transform_duplicate_definitions_with_function_and_global():
    sources = dd(
        [
            "x = 10",
            """
def func():
    global x
    x_1 = x + 1
    return x
""",
            """
x = func()
print(x)
""",
            """
def another_func():
   x = 20
   return x
""",
            """
x = another_func()
print(x)
""",
        ]
    )
    expected = dd(
        [
            "x = 10",
            """
def func():
    global x
    x_1 = x + 1
    return x
""",
            """
x_1 = func()
print(x_1)
""",
            """
def another_func():
   x = 20
   return x
""",
            """
x_2 = another_func()
print(x_2)
""",
        ]
    )

    result = transform_duplicate_definitions(sources)
    assert_sources_equal(result, expected)


def test_transform_duplicate_definitions_with_comprehensions_and_lambdas():
    sources = [
        "x = [i for i in range(5)]",
        "x = list(map(lambda x: x**2, x))\nprint(x)",
        "x = {x: x**3 for x in x}\nprint(x)",
        "x = lambda x: x**4\nprint([x(i) for i in range(5)])",
    ]
    result = transform_duplicate_definitions(sources)
    assert_sources_equal(
        result,
        dd(
            [
                "x = [i for i in range(5)]",
                "x_1 = list(map(lambda x: x**2, x))\nprint(x_1)",
                "x_2 = {x: x**3 for x in x_1}\nprint(x_2)",
                "x_3 = lambda x: x**4\nprint([x_3(i) for i in range(5)])",
            ]
        ),
    )


def test_transform_duplicate_definitions_with_simple_lambda():
    sources = [
        "x = 0",
        "x = lambda x: x**2",
    ]
    result = transform_duplicate_definitions(sources)
    assert_sources_equal(
        result,
        dd(
            [
                "x = 0",
                "x_1 = lambda x: x**2",
            ]
        ),
    )


def test_transform_simple_redefinition() -> None:
    sources = [
        "x = 0",
        "x",
        "x = 1",
        "x",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "x = 0",
        "x",
        "x_1 = 1",
        "x_1",
    ]


def test_transform_duplicate_definitions_with_simple_function():
    sources = [
        "x = 0",
        "x = 1",
        "def f(x): return x",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "x = 0",
        "x_1 = 1",
        "def f(x): return x",
    ]


def test_transform_duplicate_definitions_attrs():
    sources = [
        "x = 0",
        "x",
        "x = x.apply()",
        "x",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "x = 0",
        "x",
        "x_1 = x.apply()",
        "x_1",
    ]


def test_transform_duplicate_definition_shadowed_definition():
    sources = dd(
        [
            "x = 0",
            "x",
            """
            x = 1
            def f():
                x = 1;
            """,
        ]
    )
    result = transform_duplicate_definitions(sources)
    assert_sources_equal(
        result,
        [
            "x = 0",
            "x",
            """
            x_1 = 1
            def f():
                x = 1;
            """,
        ],
    )


def test_transform_duplicate_definition_kwarg():
    sources = dd(
        [
            "x = 0",
            "x",
            """
            x = 1
            def f(x=x):
                return x
            """,
        ]
    )
    result = transform_duplicate_definitions(sources)
    assert_sources_equal(
        result,
        [
            "x = 0",
            "x",
            """
            x_1 = 1
            def f(x=x_1):
                return x
            """,
        ],
    )


def test_transform_duplicate_definition_nested():
    sources = dd(
        [
            "x = 0",
            "x",
            """
            x = 1
            def f(x=x):
                x = 2
                def g(x=x):
                    return x
                return g()
            """,
        ]
    )
    result = transform_duplicate_definitions(sources)
    assert_sources_equal(
        result,
        [
            "x = 0",
            "x",
            """
            x_1 = 1
            def f(x=x_1):
                x = 2
                def g(x=x):
                    return x
                return g()
            """,
        ],
    )


def test_transform_duplicate_function_definitions():
    sources = dd(
        [
            "def f(): pass",
            "f()",
            "def f(): pass",
            "f()",
        ]
    )
    result = transform_duplicate_definitions(sources)
    assert_sources_equal(
        result,
        [
            "def f(): pass",
            "f()",
            "def f_1(): pass",
            "f_1()",
        ],
    )


def test_transform_duplicate_classes():
    sources = dd(
        [
            "class A(): ...",
            "A()",
            "class A(): ...",
            "A()",
        ]
    )
    result = transform_duplicate_definitions(sources)
    assert_sources_equal(
        result,
        [
            "class A(): ...",
            "A()",
            "class A_1(): ...",
            "A_1()",
        ],
    )


def test_transform_duplicate_definitions_numbered_no_conflict():
    sources = dd(
        [
            "df = 1",
            "df_1 = 1",
            "df",
        ]
    )
    result = transform_duplicate_definitions(sources)
    assert_sources_equal(
        result,
        [
            "df = 1",
            "df_1 = 1",
            "df",
        ],
    )


def test_transform_duplicate_definitions_numbered():
    # handle the user defining variables like df_1
    sources = dd(
        [
            "df = 1",
            "df_1 = 1",
            "df = 2",
            "df",
            "df = 3",
            "df",
        ]
    )
    result = transform_duplicate_definitions(sources)
    assert_sources_equal(
        result,
        [
            "df = 1",
            "df_1 = 1",
            "df_2 = 2",
            "df_2",
            "df_3 = 3",
            "df_3",
        ],
    )


def test_transform_duplicate_definitions_and_aug_assign() -> None:
    sources = dd(
        [
            "x = 1",
            "x",
            "x += 1",
            "x",
        ]
    )
    result = _transform_sources(sources, [{} for _ in sources])
    assert_sources_equal(
        result,
        [
            "x = 1",
            "x",
            "x_1 = x + 1",
            "x_1",
        ],
    )


def test_transform_duplicate_definitions_read_before_write() -> None:
    sources = dd(
        [
            "x = 1",
            "x",
            "x; x = 2; x",
            "x",
        ]
    )
    result = _transform_sources(sources, [{} for _ in sources])
    assert_sources_equal(
        result,
        [
            "x = 1",
            "x",
            "x; x_1 = 2; x_1",
            "x_1",
        ],
    )


def test_transform_duplicate_definitions_syntax_error() -> None:
    sources = dd(
        [
            "x ( b 2 d & !",
            "x",
        ]
    )
    result = _transform_sources(sources, [{} for _ in sources])
    assert_sources_equal(
        result,
        [
            "x ( b 2 d & !",
            "x",
        ],
    )
