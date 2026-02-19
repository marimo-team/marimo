from __future__ import annotations

import pytest

from marimo._plugins import ui


def test_vector_basic_column():
    v = ui.vector([1, 2, 3])
    assert v.value == [1, 2, 3]


def test_vector_transposed_row():
    v = ui.vector([1, 2, 3], transpose=True)
    assert v.value == [1, 2, 3]


def test_vector_single_element():
    v = ui.vector([5])
    assert v.value == [5]


def test_vector_with_scalar_bounds():
    v = ui.vector([0, 0, 0], min_value=-10, max_value=10, step=0.5)
    assert v.value == [0, 0, 0]


def test_vector_with_per_element_bounds():
    v = ui.vector([1, 2, 3], min_value=[0, 1, 2], max_value=[5, 6, 7])
    assert v.value == [1, 2, 3]


def test_vector_with_per_element_step():
    v = ui.vector([0, 0], step=[0.1, 0.5])
    assert v.value == [0, 0]


def test_vector_with_per_element_disabled():
    v = ui.vector([1, 2, 3], disabled=[True, False, True])
    assert v.value == [1, 2, 3]


def test_vector_scalar_disabled():
    v = ui.vector([1, 2], disabled=True)
    assert v.value == [1, 2]


def test_vector_entry_labels_column():
    """entry_labels should map to row_labels for a column vector."""
    v = ui.vector([1, 2, 3], entry_labels=["x", "y", "z"])
    assert v._component_args["row-labels"] == ["x", "y", "z"]
    assert v._component_args["column-labels"] is None


def test_vector_entry_labels_transposed():
    """entry_labels should map to column_labels for a row vector."""
    v = ui.vector([1, 2, 3], transpose=True, entry_labels=["a", "b", "c"])
    assert v._component_args["column-labels"] == ["a", "b", "c"]
    assert v._component_args["row-labels"] is None


def test_vector_convert_value():
    v = ui.vector([1, 2, 3])
    # Column vector: 2D is [[1], [2], [3]]
    result = v._convert_value([[10], [20], [30]])
    assert result == [10, 20, 30]


def test_vector_convert_value_transposed():
    v = ui.vector([1, 2, 3], transpose=True)
    # Row vector: 2D is [[1, 2, 3]]
    result = v._convert_value([[10, 20, 30]])
    assert result == [10, 20, 30]


def test_vector_update():
    v = ui.vector([1, 2, 3])
    v._update([[10], [20], [30]])
    assert v.value == [10, 20, 30]


def test_vector_update_transposed():
    v = ui.vector([1, 2], transpose=True)
    v._update([[10, 20]])
    assert v.value == [10, 20]


def test_vector_scientific():
    v = ui.vector([0.001, 1000], scientific=True, precision=2)
    assert v.value == [0.001, 1000]


def test_vector_debounce():
    v = ui.vector([1, 2], debounce=True)
    assert v._component_args["debounce"] is True


def test_vector_precision_explicit():
    v = ui.vector([1.0], precision=5)
    assert v._component_args["precision"] == 5


def test_vector_precision_default_integers():
    """Integer data with default step=1 → precision 0."""
    v = ui.vector([1, 2, 3])
    assert v._component_args["precision"] == 0


def test_vector_precision_default_float_step():
    """Float step should drive inferred precision."""
    v = ui.vector([0, 0], step=0.1)
    assert v._component_args["precision"] == 1


def test_vector_precision_default_float_data():
    """Float data values should drive inferred precision."""
    v = ui.vector([1.5, 2.333])
    assert v._component_args["precision"] == 3


def test_vector_label():
    v = ui.vector([1, 2], label="test label")
    assert v.value == [1, 2]


def test_vector_numpy_array():
    """Test that 1D array-like objects with .tolist() are accepted."""

    class FakeArray1D:
        def tolist(self):
            return [1.0, 2.0, 3.0]

    v = ui.vector(FakeArray1D())
    assert v.value == [1.0, 2.0, 3.0]


def test_vector_numpy_bounds():
    """Test that 1D array-like bounds are accepted."""

    class FakeArray1D:
        def tolist(self):
            return [0.0, 0.0]

    class FakeMins:
        def tolist(self):
            return [-5.0, -10.0]

    class FakeMaxs:
        def tolist(self):
            return [5.0, 10.0]

    v = ui.vector(FakeArray1D(), min_value=FakeMins(), max_value=FakeMaxs())
    assert v.value == [0.0, 0.0]


# --- Validation error tests ---


def test_vector_empty_raises():
    with pytest.raises(ValueError, match="non-empty"):
        ui.vector([])


def test_vector_non_list_raises():
    with pytest.raises(ValueError, match="list or 1D"):
        ui.vector("not a vector")


def test_vector_nested_raises():
    with pytest.raises(ValueError, match="1D"):
        ui.vector([[1, 2], [3, 4]])


def test_vector_min_ge_max_raises():
    with pytest.raises(ValueError, match="less than"):
        ui.vector([5], min_value=10, max_value=5)


def test_vector_value_below_min_raises():
    with pytest.raises(ValueError, match="less than min_value"):
        ui.vector([0], min_value=1)


def test_vector_value_above_max_raises():
    with pytest.raises(ValueError, match="greater than max_value"):
        ui.vector([10], max_value=5)


def test_vector_step_zero_raises():
    with pytest.raises(ValueError, match="step.*positive"):
        ui.vector([1], step=0)


def test_vector_step_negative_raises():
    with pytest.raises(ValueError, match="step.*positive"):
        ui.vector([1], step=-0.5)


def test_vector_entry_labels_mismatch_raises():
    with pytest.raises(ValueError, match="row_labels"):
        ui.vector([1, 2, 3], entry_labels=["a"])


def test_vector_entry_labels_transposed_mismatch_raises():
    with pytest.raises(ValueError, match="column_labels"):
        ui.vector([1, 2, 3], transpose=True, entry_labels=["a"])


def test_vector_bounds_length_mismatch_raises():
    with pytest.raises(ValueError, match="rows"):
        ui.vector([1, 2], min_value=[0, 0, 0])


def test_vector_negative_precision_raises():
    with pytest.raises(ValueError, match="precision"):
        ui.vector([1], precision=-1)


def test_vector_2d_param_raises():
    """1D params that are actually 2D should be rejected."""
    with pytest.raises(ValueError, match="1D"):
        ui.vector([1, 2], step=[[0.1, 0.2], [0.3, 0.4]])


def test_vector_symmetric_not_exposed():
    """vector should always set symmetric to False."""
    v = ui.vector([1, 2])
    assert v._component_args["symmetric"] is False


def test_vector_uses_matrix_plugin():
    """vector should use the marimo-matrix frontend component."""
    v = ui.vector([1, 2])
    assert v._name == "marimo-matrix"
