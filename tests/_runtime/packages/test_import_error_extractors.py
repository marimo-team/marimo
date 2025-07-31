# Copyright 2025 Marimo. All rights reserved.

import pytest

from marimo._runtime.packages.import_error_extractors import (
    extract_missing_module_from_cause_chain,
    extract_packages_from_pip_install_suggestion,
    extract_packages_special_cases,
)


def test_extract_missing_module_from_cause_chain_direct():
    """Test direct ModuleNotFoundError (no cause chain)."""
    module_error = ModuleNotFoundError("No module named 'numpy'")
    module_error.name = "numpy"

    result = extract_missing_module_from_cause_chain(module_error)
    assert result == "numpy"


def test_extract_missing_module_from_cause_chain_with_cause():
    """Test ImportError with ModuleNotFoundError cause."""
    module_error = ModuleNotFoundError("No module named 'numpy'")
    module_error.name = "numpy"

    import_error = ImportError("Custom message")
    import_error.__cause__ = module_error

    result = extract_missing_module_from_cause_chain(import_error)
    assert result == "numpy"


def test_extract_missing_module_from_cause_chain_nested():
    """Test nested cause chain."""
    root_error = ModuleNotFoundError("No module named 'pandas'")
    root_error.name = "pandas"

    middle_error = ImportError("Middle error")
    middle_error.__cause__ = root_error

    top_error = ImportError("Top error")
    top_error.__cause__ = middle_error

    result = extract_missing_module_from_cause_chain(top_error)
    assert result == "pandas"


def test_extract_missing_module_from_cause_chain_no_module():
    """Test error with no module in chain."""
    import_error = ImportError("No useful cause")
    result = extract_missing_module_from_cause_chain(import_error)
    assert result is None


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        # Simple cases
        ("Try: pip install requests", ["requests"]),
        ("Run: pip install pandas[all]", ["pandas[all]"]),
        # Quoted commands (multiple packages)
        ("Try `pip install -U polars anywidget`", ["polars", "anywidget"]),
        (
            'Run "pip install --upgrade requests pandas[all]"',
            ["requests", "pandas[all]"],
        ),
        ("Execute 'pip install -U numpy matplotlib'", ["numpy", "matplotlib"]),
        # Additional quoted edge cases
        ("Try: `pip install pandas`.", ["pandas"]),  # trailing punctuation
        ('Try running `"pip install seaborn"`', ["seaborn"]),  # nested quotes
        (
            "Use: 'pip install   scipy   matplotlib'",
            ["scipy", "matplotlib"],
        ),  # extra spaces
        (
            "Here's the command: `pip install jupyterlab` for notebooks",
            ["jupyterlab"],
        ),
        # Unquoted with surrounding text (conservative parsing)
        ("Try: pip install polars if you want to do something", ["polars"]),
        ("You can pip install requests pandas but maybe not", ["requests"]),
        # No match
        ("Some other error message", None),
        # Harder, https://github.com/flekschas/jupyter-scatter/blob/ecfd8c4e19a1ad202372c09939682e5fbe9e70ba/jscatter/dependencies.py#L33-L37
        (
            """Please install it with: pip install "jupyter-scatter[blah]" or pip install "jupyter-scatter[all]".""",
            ["jupyter-scatter[blah]"],
        ),
        ('Try: `pip install foo bar "baz[all]"`.', ["foo", "bar", "baz[all]"]),
        ("Try: `pip install foo bar 'baz[all]'`.", ["foo", "bar", "baz[all]"]),
    ],
)
def test_extract_packages_from_pip_install_suggestion(message, expected):
    """Test pip install suggestion extraction with various formats."""
    result = extract_packages_from_pip_install_suggestion(message)
    assert result == expected


def test_extract_packages_special_cases_pandas_parquet():
    """Test pandas parquet special case."""
    message = "Unable to find a usable engine; tried using: 'pyarrow', 'fastparquet'."
    result = extract_packages_special_cases(message)
    assert result == ["pyarrow"]
