from __future__ import annotations

import pytest

from marimo._convert.ipynb import (
    transform_add_marimo_import,
    transform_cell_metadata,
    transform_duplicate_definitions,
    transform_exclamation_mark,
    transform_fixup_multiple_definitions,
    transform_inline_plots,
    transform_magic_commands,
    transform_remove_duplicate_imports,
)


def test_transform_fixup_multiple_definitions():
    # Makes everything private to avoid conflicts.
    # Comments are removed, unfortunately.
    sources = ["x = 1\nprint(x) # print", "x = 2\nprint(x) # print"]
    result = transform_fixup_multiple_definitions(sources)
    assert result == ["_x = 1\nprint(_x)", "_x = 2\nprint(_x)"]


def test_transform_fixup_multiple_definitions_when_not_encapsulated():
    # Since the definitions are not encapsulated in a single cell, they should
    # not be transformed.
    sources = ["x = 1", "print(x) # print", "x = 2", "print(x) # print"]
    result = transform_fixup_multiple_definitions(sources)
    assert result == sources


def test_transform_add_marimo_import():
    sources = [
        "mo.md('# Hello')",
        "print('World')",
        "mo.sql('SELECT * FROM table')",
    ]
    result = transform_add_marimo_import(sources)
    assert "import marimo as mo" in result


def test_transform_magic_commands():
    sources = [
        "%%sql\nSELECT * FROM table",
        "%%sql\nSELECT * \nFROM table",
        "%cd /path/to/dir",
        "%matplotlib inline",
    ]
    result = transform_magic_commands(sources)
    assert result == [
        '_df = mo.sql("""\nSELECT * FROM table\n""")',
        '_df = mo.sql("""\nSELECT * \nFROM table\n""")',
        "import os\nos.chdir('/path/to/dir')",
        "# '%matplotlib inline' command supported automatically in marimo",
    ]


def test_transform_inline_plots():
    sources = ["plt.plot([1, 2, 3])", "plt.show()"]
    result = transform_inline_plots(sources)
    assert result == ["plt.plot([1, 2, 3])", "plt.gcf()"]


def test_transform_exclamation_mark():
    sources = ["!pip install package", "!ls -l"]
    result = transform_exclamation_mark(sources)
    assert result == [
        "# (already supported in marimo) !pip install package",
        "!ls -l",
    ]


def test_transform_duplicate_definitions():
    sources = ["a = 1", "print(a)", "a = 2", "print(a)", "print(a)", "a = 3"]
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
    sources = ["print('Hello')", "print('World')"]
    metadata = [{"tags": ["tag1", "tag2"]}, {}]
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
    assert result == ["import polars as pl", ""]


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
    assert (
        result
        == [
            '_df = mo.sql("""\nSELECT *\nFROM table\nWHERE condition\n""")',
            (
                "# magic command not supported in marimo; please file an issue to add support\n"  # noqa: E501
                "# %%time\nfor i in range(1000000):\n"
                "    pass"
            ),
            (
                "# '%load_ext autoreload\\n%autoreload 2' command supported automatically in marimo"  # noqa: E501
            ),
            "import os\nos.environ['MY_VAR'] = 'value'",
        ]
    )


def test_transform_inline_plots_complex():
    sources = [
        "fig, ax = plt.subplots()\nax.plot([1, 2, 3])\nplt.show()",
        "plt.figure()\nplt.plot([4, 5, 6])\nplt.title('My Plot')\nplt.show()",
        "sns.scatterplot(x='col1', y='col2', data=df)\nplt.show()",
    ]
    result = transform_inline_plots(sources)
    assert result == [
        "fig, ax = plt.subplots()\nax.plot([1, 2, 3])\nplt.gcf()",
        "plt.figure()\nplt.plot([4, 5, 6])\nplt.title('My Plot')\nplt.gcf()",
        "sns.scatterplot(x='col1', y='col2', data=df)\nplt.gcf()",
    ]


def test_transform_exclamation_mark_complex():
    sources = [
        "!pip install package1 package2",
        "! ls -l | grep '.py'",
        "result = !echo 'Hello, World!'",
        "!python script.py arg1 arg2",
    ]
    result = transform_exclamation_mark(sources)
    assert result == [
        "# (already supported in marimo) !pip install package1 package2",
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
    sources = ["print('Cell 1')", "print('Cell 2')", "print('Cell 3')"]
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
    sources = ["%custom_magic arg1 arg2", "%%custom_cell_magic\nsome\ncontent"]
    result = transform_magic_commands(sources)
    assert result == [
        "# magic command not supported in marimo; please file an issue to add support\n# %custom_magic # arg1 arg2",  # noqa: E501
        "# magic command not supported in marimo; please file an issue to add support\n# %%custom_cell_magic\n# some\n# content",  # noqa: E501
    ]


def test_transform_inline_plots_with_custom_plotting():
    sources = [
        "import seaborn as sns",
        "sns.heatmap(data)\nplt.show()",
        "fig = plt.figure()\nax = fig.add_subplot(111, projection='3d')\nax.scatter(xs, ys, zs)\nplt.show()",  # noqa: E501
    ]
    result = transform_inline_plots(sources)
    assert result == [
        "import seaborn as sns",
        "sns.heatmap(data)\nplt.gcf()",
        "fig = plt.figure()\nax = fig.add_subplot(111, projection='3d')\nax.scatter(xs, ys, zs)\nplt.gcf()",  # noqa: E501
    ]


def test_transform_exclamation_mark_with_variables():
    sources = [
        "package = 'numpy'\n!pip install {package}",
        "command = 'echo \"Hello, World!\"'\n!{command}",
    ]
    result = transform_exclamation_mark(sources)
    assert result == [
        "package = 'numpy'\n# (already supported in marimo) !pip install {package}",  # noqa: E501
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
        "x_1 = x\nx_1 = x_1 + 1\nprint(x_1)",
        "print(x_1)",
    ]


def test_transform_cell_metadata_with_complex_metadata():
    sources = ["print('Complex metadata')"]
    metadata = [
        {
            "tags": ["tag1", "tag2"],
            "collapsed": True,
            "scrolled": False,
            "custom": {"key": "value"},
        }
    ]
    result = transform_cell_metadata(sources, metadata)
    assert result == ["# Cell tags: tag1, tag2\nprint('Complex metadata')"]


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
        "x_1 = x\nx_1 = x_1 + 1\nprint(x_1)",
        "x_2 = x_1\nx_2 = x_2 + 2\nprint(x_2)",
        "x_3 = x_2\nx_3 = x_3 + 3\nprint(x_3)",
        "x_4 = 10\nprint(x_4)",
        "print(x_4)",
    ]


@pytest.mark.skip(reason="tricky case not yet supported")
def test_transform_duplicate_definitions_with_multiple_variables():
    sources = [
        "x, y = 1, 2",
        "x = x + y\ny = y + x\nprint(x, y)",
        "z = x + y\nx = z\nprint(x, y, z)",
        "x, y, z = y, z, x\nprint(x, y, z)",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "x, y = 1, 2",
        "x_1 = x\ny_1 = y\nx_1 = x_1 + y_1\ny_1 = y_1 + x_1\nprint(x_1, y_1)",
        "z = x_1 + y_1\nx_2 = z\nprint(x_2, y_1, z)",
        "x_3, y_2, z_1 = (y_1, z, x_2)\nprint(x_3, y_2, z_1)",
    ]


@pytest.mark.skip(reason="tricky case not yet supported")
def test_transform_duplicate_definitions_with_function_and_global():
    sources = [
        "x = 10",
        "def func():\n    global x\n    x += 1\n    return x",
        "x = func()\nprint(x)",
        "def another_func():\n    x = 20\n    return x",
        "x = another_func()\nprint(x)",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "x = 10",
        "def func():\n    global x\n    x += 1\n    return x",
        "x_1 = func()\nprint(x_1)",
        "def another_func():\n    x = 20\n    return x",
        "x_2 = another_func()\nprint(x_2)",
    ]


@pytest.mark.skip(reason="tricky case not yet supported")
def test_transform_duplicate_definitions_with_comprehensions_and_lambdas():
    sources = [
        "x = [i for i in range(5)]",
        "x = list(map(lambda x: x**2, x))\nprint(x)",
        "x = {x: x**3 for x in x}\nprint(x)",
        "x = lambda x: x**4\nprint([x(i) for i in range(5)])",
    ]
    result = transform_duplicate_definitions(sources)
    assert result == [
        "x = [i for i in range(5)]",
        "x_1 = x\nx_1 = list(map(lambda x: x**2, x_1))\nprint(x_1)",
        "x_2 = x_1\nx_2 = {x: x**3 for x in x_2}\nprint(x_2)",
        "x_3 = lambda x: x**4\nprint([x_3(i) for i in range(5)])",
    ]
