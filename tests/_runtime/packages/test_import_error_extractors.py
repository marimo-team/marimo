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
        # Unquoted with surrounding text (conservative parsing)
        ("Try: pip install polars if you want to do something", ["polars"]),
        ("You can pip install requests pandas but maybe not", ["requests"]),
        # No match
        ("Some other error message", None),
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
