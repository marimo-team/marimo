from __future__ import annotations

import ast
import json
from textwrap import dedent

import pytest

from marimo._convert.ipynb.to_ir import (
    CellsTransform,
    CodeCell,
    Transform,
    convert_from_ipynb_to_notebook_ir,
    transform_add_marimo_import,
    transform_add_subprocess_import,
    transform_duplicate_definitions,
    transform_exclamation_mark,
    transform_fixup_multiple_definitions,
    transform_magic_commands,
    transform_remove_duplicate_imports,
)


def dd(sources: list[str]) -> list[str]:
    return [dedent(s) for s in sources]


def strip_cells(transform: CellsTransform) -> Transform:
    """Test wrapper for cell transforms - extracts only source content for testing."""

    def wrapped(sources: list[str]) -> list[str]:
        cells = [CodeCell(s) for s in sources]
        return [cell.source for cell in transform(cells)]

    return wrapped


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
    result = strip_cells(transform_add_marimo_import)(sources)
    assert result == ["import marimo as mo"] + sources

    # mo.sql
    sources = [
        "mo.sql('SELECT * FROM table')",
        "print('World')",
    ]
    result = strip_cells(transform_add_marimo_import)(sources)
    assert result == ["import marimo as mo"] + sources

    # if `import marimo as mo` is already present
    # it should not be added again
    existing = sources + ["import marimo as mo"]
    assert strip_cells(transform_add_marimo_import)(existing) == existing

    existing = [
        # slight support for different import orders
        # but must use canonical "import marimo as mo" form
        "import antigravity; import marimo as mo",
        "mo.md('# Hello')",
    ]
    assert strip_cells(transform_add_marimo_import)(existing) == existing


def test_transform_add_marimo_import_already_imported():
    sources = [
        "import marimo as mo",
        "mo.md('# Hello')",
        "print('World')",
    ]
    result = strip_cells(transform_add_marimo_import)(sources)
    assert result == sources


def test_transform_add_marimo_import_already_but_in_comment_or_definition():
    # Comment
    sources = [
        "mo.md('# Hello')",
        "# import marimo as mo",
    ]
    result = strip_cells(transform_add_marimo_import)(sources)
    assert result == ["import marimo as mo"] + sources

    # Definition
    sources = [
        "mo.md('# Hello')",
        "def foo():\n    import marimo as mo",
    ]
    result = strip_cells(transform_add_marimo_import)(sources)
    assert result == ["import marimo as mo"] + sources


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
    assert result.transformed_sources == [
        "# packages added via marimo's package management: package !pip install package",
        "#! ls -l\nsubprocess.call(['ls', '-l'])",
    ]
    assert result.pip_packages == ["package"]
    assert result.needs_subprocess is True


def test_complex_exclamation_mark():
    sources = [
        """!uv pip install --upgrade \\
            openpipe-art[backend,langgraph]==0.4.11 langchain-core langgraph langchain_openai tenacity datasets pillow==11.3.0 protobuf==5.29.5 {get_vllm} {get_numpy} --prerelease allow --no-cache-dir"""
    ]
    result = transform_exclamation_mark(sources)
    # Packages are unpinned, normalized per PEP 503, and sorted
    assert result.pip_packages == [
        "datasets",
        "langchain-core",
        "langchain-openai",  # normalized from langchain_openai
        "langgraph",
        "openpipe-art",
        "pillow",
        "protobuf",
        "tenacity",
    ]
    assert result.transformed_sources == [
        "# packages added via marimo's package management: openpipe-art[backend,langgraph]==0.4.11 langchain-core langgraph langchain_openai tenacity datasets pillow==11.3.0 protobuf==5.29.5 !uv pip install --upgrade openpipe-art[backend,langgraph]==0.4.11 langchain-core langgraph langchain_openai tenacity datasets pillow==11.3.0 protobuf==5.29.5 {get_vllm} {get_numpy} --prerelease allow --no-cache-dir",
    ]
    assert result.needs_subprocess is False


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


def test_transform_remove_duplicate_imports():
    sources = [
        "import numpy as np\nimport pandas as pd\nimport numpy as np",
        "from sklearn.model_selection import train_test_split\nfrom sklearn.model_selection import cross_val_score",
        "import matplotlib.pyplot as plt\nimport numpy as np",
    ]
    result = transform_remove_duplicate_imports(sources)
    assert result == [
        "import numpy as np\nimport pandas as pd",
        "from sklearn.model_selection import train_test_split\nfrom sklearn.model_selection import cross_val_score",
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
    result = strip_cells(transform_add_marimo_import)(sources)
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
            "# magic command not supported in marimo; please file an issue to add support\n"
            "# %%time\nfor i in range(1000000):\n"
            "    pass"
        ),
        (
            "# magic command not supported in marimo; please file an issue to add support\n"
            "# %load_ext autoreload\n"
            "# '%autoreload 2' command supported automatically in marimo"
        ),
        "import os\nos.environ['MY_VAR'] = 'value'",
    ]
    assert result == expected


def test_transform_exclamation_mark_complex():
    sources = [
        "!pip install package1 package2",
        "!ls -l",
        "!echo 'Hello, World!'",
        "!python script.py arg1 arg2",
        "!python -m pip3 install package1 package2",
        "!uv pip install package1 package2",
    ]
    result = transform_exclamation_mark(sources)
    assert result.transformed_sources == [
        "# packages added via marimo's package management: package1 package2 !pip install package1 package2",
        "#! ls -l\nsubprocess.call(['ls', '-l'])",
        "#! echo 'Hello, World!'\nsubprocess.call(['echo', 'Hello, World!'])",
        "#! python script.py arg1 arg2\nsubprocess.call(['python', 'script.py', 'arg1', 'arg2'])",
        "# packages added via marimo's package management: package1 package2 !python -m pip3 install package1 package2",
        "# packages added via marimo's package management: package1 package2 !uv pip install package1 package2",
    ]


def test_transform_exclamation_mark_with_indentation():
    # Indented pip installs get pass, non-pip commands use subprocess
    sources = [
        "if True:\n    !pip install numpy",
        "for i in range(10):\n    !echo test",
    ]
    result = transform_exclamation_mark(sources)
    # Pip gets pass + package management, echo uses subprocess
    assert result.transformed_sources == [
        "if True:\n    pass  # packages added via marimo's package management: numpy !pip install numpy",
        "for i in range(10):\n    #! echo test\n    subprocess.call(['echo', 'test'])",
    ]
    # Packages extracted even when indented
    assert result.pip_packages == ["numpy"]
    assert result.needs_subprocess is True


def test_transform_exclamation_mark_indented_multiline():
    """Test indented multi-line command with backslash continuation"""
    sources = ["if something:\n    !echo 12\\\n      34"]
    result = transform_exclamation_mark(sources)
    # Should handle backslash continuation and preserve indentation
    assert "subprocess.call" in result.transformed_sources[0]
    assert "echo" in result.transformed_sources[0]
    assert result.needs_subprocess is True
    # Verify indentation is preserved for the subprocess call
    assert "    subprocess.call" in result.transformed_sources[0]
    # The command should have combined "12" and "34" after removing continuation
    assert "12" in result.transformed_sources[0]
    assert "34" in result.transformed_sources[0]


def test_transform_exclamation_mark_preserves_comments():
    sources = [
        "!ls -l  # list files",
        "!pip install numpy  # install numpy",
    ]
    result = transform_exclamation_mark(sources)
    # Comments should be preserved on the next line
    assert "# list files" in result.transformed_sources[0]
    assert "subprocess.call" in result.transformed_sources[0]
    assert "# install numpy" in result.transformed_sources[1]


def test_transform_exclamation_mark_pip_variants():
    sources = [
        "!pip install numpy",
        "!pip3 install pandas",
        "!pip install -U matplotlib",
        "!pip install --upgrade seaborn",
    ]
    result = transform_exclamation_mark(sources)
    assert all("# packages" in r for r in result.transformed_sources)


def test_transform_exclamation_mark_pip_non_install():
    sources = [
        "!pip upgrade",
        "!pip --version",
        "!pip",
    ]
    result = transform_exclamation_mark(sources)
    # Non-install pip commands should be treated as subprocess calls
    assert all(
        "# packages" not in r and "#! pip" in r and "subprocess.call" in r
        for r in result.transformed_sources
    )


def test_transform_exclamation_mark_not_at_line_start():
    # ! must be at the start of a line (after newline)
    sources = [
        'x = "!pip install numpy"',  # In string
        "y = 5 !",  # Not at line start
    ]
    result = transform_exclamation_mark(sources)
    # Should not transform these
    assert result.transformed_sources[0] == 'x = "!pip install numpy"'
    # Second one might cause tokenization error, so just check it doesn't crash


def test_transform_exclamation_mark_multiline_cell():
    sources = [
        "import os\n!pip install numpy\nprint('done')",
        "x = 1\n!ls -l\ny = 2",
    ]
    result = transform_exclamation_mark(sources)
    assert (
        "# packages added via marimo's package management:"
        in result.transformed_sources[0]
    )
    assert "print('done')" in result.transformed_sources[0]
    assert "subprocess.call" in result.transformed_sources[1]
    assert "x = 1" in result.transformed_sources[1]
    assert "y = 2" in result.transformed_sources[1]


def test_transform_exclamation_mark_quoted_args():
    sources = [
        '!echo "hello world"',
        "!grep 'pattern' file.txt",
    ]
    result = transform_exclamation_mark(sources)
    assert result.transformed_sources == [
        "#! echo \"hello world\"\nsubprocess.call(['echo', 'hello world'])",
        "#! grep 'pattern' file.txt\nsubprocess.call(['grep', 'pattern', 'file.txt'])",
    ]


def test_transform_exclamation_mark_empty_command():
    sources = [
        "!",
        "!   ",
    ]
    result = transform_exclamation_mark(sources)
    # Should handle gracefully
    assert len(result.transformed_sources) == 2


def test_transform_exclamation_in_multiline_string():
    sources = [
        """'''
! this is just a string'''
"""
    ]
    result = transform_exclamation_mark(sources)
    # Should handle gracefully - returns unchanged source
    assert len(result.transformed_sources) == 1
    assert result.transformed_sources[0] == sources[0]


def test_transform_exclamation_mark_pip_in_string():
    """Ensure !pip install inside strings is NOT transformed"""
    sources = [
        '''"""
!pip install numpy
"""'''
    ]
    result = transform_exclamation_mark(sources)
    # Should NOT be transformed - it's inside a string
    assert result.transformed_sources[0] == sources[0]
    # Should NOT extract packages from strings
    assert result.pip_packages == []
    assert result.needs_subprocess is False


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


def test_transform_remove_duplicate_imports_complex():
    sources = [
        "import numpy as np\nfrom pandas import DataFrame\nimport matplotlib.pyplot as plt",
        "from sklearn.model_selection import train_test_split, cross_val_score\nimport numpy as np",
        "from pandas import Series\nfrom matplotlib import pyplot as plt\nimport pandas as pd",
    ]
    result = transform_remove_duplicate_imports(sources)
    assert result == [
        "import numpy as np\nfrom pandas import DataFrame\nimport matplotlib.pyplot as plt",
        "from sklearn.model_selection import train_test_split, cross_val_score",
        "from pandas import Series\nimport pandas as pd",
    ]


def test_transform_fixup_multiple_definitions_with_classes():
    sources = [
        "class MyClass:\n    x = 1\n    def method(self):\n        return self.x",
        "x = 2\nprint(x)",
        "class MyClass:\n    x = 3\n    def method(self):\n        return self.x",
    ]
    result = transform_fixup_multiple_definitions(sources)
    assert result == [
        "class _MyClass:\n    x = 1\n\n    def method(self):\n        return self.x",
        "x = 2\nprint(x)",
        "class _MyClass:\n    x = 3\n\n    def method(self):\n        return self.x",
    ]


def test_transform_magic_commands_unsupported():
    sources = [
        "%custom_magic arg1 arg2",
        "%%custom_cell_magic\nsome\ncontent",
    ]
    result = transform_magic_commands(sources)
    assert result == [
        "# magic command not supported in marimo; please file an issue to add support\n# %custom_magic arg1 arg2",
        "# magic command not supported in marimo; please file an issue to add support\n# %%custom_cell_magic\n# some\n# content",
    ]


def test_transform_exclamation_mark_with_variables():
    # Note: Jupyter's {variable} interpolation in ! commands doesn't work in Python
    # We transform them anyway since they're ! commands
    sources = [
        "package = 'numpy'\n!pip install {package}",
        "command = 'echo \"Hello, World!\"'\n!{command}",
        "value = 42\n!echo {value}",
    ]
    result = transform_exclamation_mark(sources)
    # These get transformed (template variables become str() calls in subprocess)
    assert result.transformed_sources == [
        "package = 'numpy'\n# packages added via marimo's package management: {package} !pip install {package}",
        "command = 'echo \"Hello, World!\"'\n#! {command}\nsubprocess.call([str(command)])",
        "value = 42\n#! echo {value}\nsubprocess.call(['echo', str(value)])",
    ]


def test_transform_exclamation_mark_with_invalid_expressions():
    # Test that invalid Python expressions in templates are caught
    # Most syntax errors fail tokenization and remain unchanged
    # But some pass tokenization and are caught by compilation check
    sources = [
        "!wget {1+*2}",  # Invalid operator sequence - caught by compilation check
        "!echo {1/0}",  # Valid syntax but would fail at runtime - still converts
    ]
    result = transform_exclamation_mark(sources)
    # First is invalid and gets pass (always for invalid commands)
    # Second is valid Python syntax (runtime error is OK)
    assert result.transformed_sources == [
        "# Note: Command contains invalid template expression\n# !wget {1+*2}",
        "#! echo {1/0}\nsubprocess.call(['echo', str(1/0)])",
    ]
    assert result.pip_packages == []
    # Second command needs subprocess
    assert result.needs_subprocess is True


def test_transform_exclamation_mark_with_safe_templates():
    # Test that safe template placeholders are converted to str() calls
    sources = [
        "!echo {value}",
        "!ls {directory}",
        "!cat {config[file]}",  # Note: shlex removes quotes, so use unquoted
    ]
    result = transform_exclamation_mark(sources)
    # Safe templates are converted to str() calls
    assert result.transformed_sources == [
        "#! echo {value}\nsubprocess.call(['echo', str(value)])",
        "#! ls {directory}\nsubprocess.call(['ls', str(directory)])",
        "#! cat {config[file]}\nsubprocess.call(['cat', str(config[file])])",
    ]
    assert result.needs_subprocess is True


def test_transform_exclamation_mark_indented_pip_install():
    """Test that indented pip installs use package management with pass"""
    sources = [
        "if True:\n    !python -m uv pip install --upgrade weave\n\nprint('done')"
    ]
    result = transform_exclamation_mark(sources)
    # Should use marimo's package management with pass
    assert (
        "pass  # packages added via marimo's package management"
        in result.transformed_sources[0]
    )
    assert "weave" in result.transformed_sources[0]
    assert result.pip_packages == ["weave"]  # Packages extracted
    assert result.needs_subprocess is False


def test_transform_exclamation_mark_indented_invalid_command():
    """Test that indented invalid commands get pass statement"""
    sources = ["if False:\n    !wget {1+*2}\n\nprint('done')"]
    result = transform_exclamation_mark(sources)
    # Invalid expression in indented context gets pass statement
    assert "pass  # !wget {1+*2}" in result.transformed_sources[0]
    assert (
        "Note: Command contains invalid template expression"
        in result.transformed_sources[0]
    )
    assert result.pip_packages == []
    assert result.needs_subprocess is False


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
        "from pandas import Series",
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


def test_transform_add_subprocess_import():
    # After transforming exclamation marks, subprocess import should be added
    sources = [
        "!ls -l",
        "print('hello')",
    ]
    # First transform exclamation marks
    exclamation_result = transform_exclamation_mark(sources)

    # Then test subprocess import addition
    cells = [
        CodeCell("subprocess.call(['ls', '-l'])"),
        CodeCell("print('hello')"),
    ]
    result = transform_add_subprocess_import(cells, exclamation_result)

    # Should have subprocess import at the beginning
    assert len(result) == 3
    assert result[0].source == "import subprocess"
    assert "subprocess.call" in result[1].source


def test_transform_add_subprocess_import_already_exists():
    sources = [
        "!echo test",
    ]
    exclamation_result = transform_exclamation_mark(sources)

    cells = [
        CodeCell("import subprocess"),
        CodeCell("subprocess.call(['echo', 'test'])"),
    ]
    result = transform_add_subprocess_import(cells, exclamation_result)

    # Should not add duplicate import
    assert len(result) == 2
    assert result[0].source == "import subprocess"


def test_transform_add_subprocess_import_not_needed():
    sources = [
        "!pip install numpy",
    ]
    exclamation_result = transform_exclamation_mark(sources)

    cells = [
        CodeCell(
            "# packages added via marimo's package management: numpy !pip install numpy"
        ),
    ]
    result = transform_add_subprocess_import(cells, exclamation_result)

    # Should not add import since only pip commands were used
    assert len(result) == 1


def test_build_metadata_with_pip_packages():
    # Create a minimal notebook with pip install
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": "!pip install numpy pandas",
                "metadata": {},
            }
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 2,
    }

    result = convert_from_ipynb_to_notebook_ir(json.dumps(notebook))

    # Check that metadata contains the pip packages
    assert 'dependencies = ["numpy", "pandas"]' in result.header.value


def test_build_metadata_no_pip_packages():
    # Create a notebook without pip install
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": "print('hello')",
                "metadata": {},
            }
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 2,
    }

    result = convert_from_ipynb_to_notebook_ir(json.dumps(notebook))

    # Should not have metadata
    assert result.header.value == ""


def test_build_metadata_with_existing_metadata():
    # Create a notebook with existing PEP 723 metadata
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": "# /// script\n# requires-python = '>=3.9'\n# ///\n\n!pip install requests",
                "metadata": {},
            }
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 2,
    }

    result = convert_from_ipynb_to_notebook_ir(json.dumps(notebook))

    # Should add dependencies to existing metadata
    assert 'dependencies = ["requests"]' in result.header.value
    assert "requires-python" in result.header.value


def test_integration_exclamation_marks_full_pipeline():
    # Test the full pipeline with mixed commands
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": "!pip install numpy\nimport numpy as np",
                "metadata": {},
            },
            {
                "cell_type": "code",
                "source": "!echo 'Processing data'",
                "metadata": {},
            },
            {
                "cell_type": "code",
                "source": "result = np.array([1, 2, 3])",
                "metadata": {},
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 2,
    }

    result = convert_from_ipynb_to_notebook_ir(json.dumps(notebook))

    # Check metadata has pip packages
    assert 'dependencies = ["numpy"]' in result.header.value

    # Check subprocess import was added
    sources = [cell.code for cell in result.cells]
    assert any("import subprocess" in s for s in sources)

    # Check transformations applied
    assert any("subprocess.call" in s for s in sources)
    assert any(
        "# packages added via marimo's package management:" in s
        for s in sources
    )


def test_transform_git_url_packages():
    from marimo._convert.ipynb.to_ir import _normalize_git_url_package

    # Test git+https URL
    result = _normalize_git_url_package(
        "git+https://github.com/locuslab/mugrade.git"
    )
    assert result == "mugrade @ git+https://github.com/locuslab/mugrade.git"

    # Test https URL (should be converted to git+https)
    result = _normalize_git_url_package(
        "https://github.com/user/mypackage.git"
    )
    assert result == "mypackage @ git+https://github.com/user/mypackage.git"

    # Test URL without .git extension
    result = _normalize_git_url_package("git+https://github.com/user/repo")
    assert result == "repo @ git+https://github.com/user/repo"

    # Test regular package (should remain unchanged)
    result = _normalize_git_url_package("numpy")
    assert result == "numpy"

    result = _normalize_git_url_package("pandas>=1.0.0")
    assert result == "pandas>=1.0.0"

    # Test GitLab URL
    result = _normalize_git_url_package(
        "git+https://gitlab.com/user/project.git"
    )
    assert result == "project @ git+https://gitlab.com/user/project.git"


def test_integration_git_url_in_notebook():
    # Test the full pipeline with git URL install
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": "!pip install --upgrade --no-deps git+https://github.com/locuslab/mugrade.git",
                "metadata": {},
            }
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 2,
    }

    result = convert_from_ipynb_to_notebook_ir(json.dumps(notebook))

    # Check that the git URL was properly converted to PEP 508 format
    assert (
        'dependencies = ["mugrade @ git+https://github.com/locuslab/mugrade.git"]'
        in result.header.value
    )


def test_integration_mixed_packages_with_git_url():
    # Test the full pipeline with mixed packages including git URLs
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": "!pip install numpy pandas git+https://github.com/user/package.git",
                "metadata": {},
            }
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 2,
    }

    result = convert_from_ipynb_to_notebook_ir(json.dumps(notebook))

    # Check that all packages are properly formatted
    header_value = result.header.value
    assert '"numpy"' in header_value
    assert '"pandas"' in header_value
    assert (
        '"package @ git+https://github.com/user/package.git"' in header_value
    )
