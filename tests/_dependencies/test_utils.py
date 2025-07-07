# Copyright 2024 Marimo. All rights reserved.

import pytest

from marimo._dependencies.utils import get_module_name


def test_get_module_name_with_name_attribute():
    """Test when ModuleNotFoundError has a name attribute."""
    exception = ModuleNotFoundError()
    exception.name = "pandas"

    result = get_module_name(exception)
    assert result == "pandas"


def test_get_module_name_with_submodule():
    """Test when the module name is a submodule."""
    exception = ModuleNotFoundError()
    exception.name = "pandas.core"

    result = get_module_name(exception)
    assert result == "pandas"


def test_get_module_name_without_name_requires_pattern():
    """Test when name is None and error message matches 'requires' pattern."""
    exception = ModuleNotFoundError(
        "This library requires 'numpy' to be installed"
    )
    exception.name = None

    result = get_module_name(exception)
    assert result == "numpy"


def test_get_module_name_without_name_requires_pattern_double_quotes():
    """Test when name is None and error message has double quotes."""
    exception = ModuleNotFoundError(
        'This library requires "matplotlib" to be installed'
    )
    exception.name = None

    result = get_module_name(exception)
    assert result == "matplotlib"


def test_get_module_with_double_quotes():
    """Test when the module name is quoted with double quotes."""
    exception = ModuleNotFoundError('No module named "pandas"')
    exception.name = None

    result = get_module_name(exception)
    assert result == "pandas"


@pytest.mark.xfail(reason="No quotes is not supported")
def test_get_module_name_without_name_requires_pattern_no_quotes():
    """Test when name is None and error message has no quotes."""
    exception = ModuleNotFoundError(
        "This library requires scipy to be installed"
    )
    exception.name = None

    result = get_module_name(exception)
    assert result == "scipy"


def test_get_module_name_start_location_quotes():
    """Test when name is None and error message matches 'module to be installed' pattern."""
    exception = ModuleNotFoundError(
        "'plotly' module to be installed for this feature"
    )
    exception.name = None

    result = get_module_name(exception)
    assert result == "plotly"


def test_get_module_name_start_location_double_quotes():
    """Test when name is None and error message has double quotes."""
    exception = ModuleNotFoundError(
        '"seaborn" module to be installed for this feature'
    )
    exception.name = None

    result = get_module_name(exception)
    assert result == "seaborn"


@pytest.mark.xfail(reason="No quotes is not supported")
def test_get_module_name_start_location_no_quotes():
    """Test when name is None and error message has no quotes."""
    exception = ModuleNotFoundError(
        "sklearn module to be installed for this feature"
    )
    exception.name = None

    result = get_module_name(exception)
    assert result == "sklearn"


def test_get_module_name_no_match():
    """Test when name is None and error message doesn't match any pattern."""
    exception = ModuleNotFoundError("Some random error message")
    exception.name = None

    with pytest.raises(ValueError):
        get_module_name(exception)


def test_get_module_name_with_complex_submodule():
    """Test with a deeply nested submodule."""
    exception = ModuleNotFoundError(
        "No module named 'tensorflow.keras.layers'"
    )
    exception.name = "tensorflow.keras.layers"

    result = get_module_name(exception)
    assert result == "tensorflow"


@pytest.mark.xfail(reason="No quotes is not supported")
def test_get_module_name_with_numbers_in_name():
    """Test with module names containing numbers."""
    exception = ModuleNotFoundError("No module named pandas2")
    exception.name = None

    result = get_module_name(exception)
    assert result == "pandas2"
