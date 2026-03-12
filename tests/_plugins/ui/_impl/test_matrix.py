from __future__ import annotations

import pytest

from marimo._plugins import ui

# =========================================================================
# 2D matrix tests (original)
# =========================================================================


def test_matrix_basic():
    m = ui.matrix([[1, 2], [3, 4]])
    assert m.value == [[1.0, 2.0], [3.0, 4.0]]


def test_matrix_debounce():
    m = ui.matrix([[1, 2], [3, 4]], debounce=True)
    assert m.value == [[1.0, 2.0], [3.0, 4.0]]


def test_matrix_single_cell():
    m = ui.matrix([[5]])
    assert m.value == [[5.0]]


def test_matrix_with_bounds():
    m = ui.matrix(
        [[0, 0], [0, 0]],
        min_value=-10,
        max_value=10,
        step=0.5,
        precision=2,
    )
    assert m.value == [[0.0, 0.0], [0.0, 0.0]]


def test_matrix_with_per_element_bounds():
    m = ui.matrix(
        [[1, 2], [3, 4]],
        min_value=[[0, 1], [2, 3]],
        max_value=[[5, 6], [7, 8]],
    )
    assert m.value == [[1.0, 2.0], [3.0, 4.0]]


def test_matrix_with_labels():
    m = ui.matrix(
        [[1, 2], [3, 4]],
        row_labels=["r1", "r2"],
        column_labels=["c1", "c2"],
    )
    assert m.value == [[1.0, 2.0], [3.0, 4.0]]


def test_matrix_symmetric():
    m = ui.matrix([[1, 2], [2, 1]], symmetric=True)
    assert m.value == [[1.0, 2.0], [2.0, 1.0]]


def test_matrix_convert_value():
    m = ui.matrix([[1, 2], [3, 4]])
    result = m._convert_value([[5, 6], [7, 8]])
    assert result == [[5, 6], [7, 8]]


def test_matrix_update():
    m = ui.matrix([[1, 2], [3, 4]])
    m._update([[10, 20], [30, 40]])
    assert m.value == [[10, 20], [30, 40]]


def test_matrix_disabled_scalar():
    m = ui.matrix([[1, 2], [3, 4]], disabled=True)
    assert m.value == [[1.0, 2.0], [3.0, 4.0]]


def test_matrix_disabled_per_element():
    m = ui.matrix(
        [[1, 2], [3, 4]],
        disabled=[[True, False], [False, True]],
    )
    assert m.value == [[1.0, 2.0], [3.0, 4.0]]


# --- 2D validation error tests ---


def test_matrix_empty_raises():
    with pytest.raises(ValueError, match="non-empty"):
        ui.matrix([])


def test_matrix_non_list_raises():
    with pytest.raises(ValueError, match="list of lists"):
        ui.matrix("not a matrix")


def test_matrix_inconsistent_rows_raises():
    with pytest.raises(ValueError, match="columns but expected"):
        ui.matrix([[1, 2], [3]])


def test_matrix_min_ge_max_raises():
    with pytest.raises(ValueError, match="less than"):
        ui.matrix([[5]], min_value=10, max_value=5)


def test_matrix_min_eq_max_raises():
    with pytest.raises(ValueError, match="less than"):
        ui.matrix([[5]], min_value=5, max_value=5)


def test_matrix_value_below_min_raises():
    with pytest.raises(ValueError, match="less than min_value"):
        ui.matrix([[0]], min_value=1)


def test_matrix_value_above_max_raises():
    with pytest.raises(ValueError, match="greater than max_value"):
        ui.matrix([[10]], max_value=5)


def test_matrix_row_labels_mismatch_raises():
    with pytest.raises(ValueError, match="row_labels"):
        ui.matrix([[1, 2], [3, 4]], row_labels=["a"])


def test_matrix_column_labels_mismatch_raises():
    with pytest.raises(ValueError, match="column_labels"):
        ui.matrix([[1, 2], [3, 4]], column_labels=["a", "b", "c"])


def test_matrix_symmetric_non_square_raises():
    with pytest.raises(ValueError, match="square"):
        ui.matrix([[1, 2, 3], [4, 5, 6]], symmetric=True)


def test_matrix_bounds_shape_mismatch_raises():
    with pytest.raises(ValueError, match="rows"):
        ui.matrix([[1, 2]], min_value=[[0, 0], [0, 0]])


def test_matrix_negative_precision_raises():
    with pytest.raises(ValueError, match="precision"):
        ui.matrix([[1]], precision=-1)


def test_matrix_scientific():
    m = ui.matrix([[0.001, 1000]], scientific=True, precision=2)
    assert m.value == [[0.001, 1000.0]]


def test_matrix_numpy_array_like():
    """Test that array-like objects with .tolist() are accepted."""

    class FakeArray:
        def tolist(self):
            return [[1.0, 2.0], [3.0, 4.0]]

    m = ui.matrix(FakeArray())
    assert m.value == [[1.0, 2.0], [3.0, 4.0]]


def test_matrix_empty_row_raises():
    with pytest.raises(ValueError, match="non-empty"):
        ui.matrix([[]])


def test_matrix_step_zero_raises():
    with pytest.raises(ValueError, match="step.*positive"):
        ui.matrix([[1]], step=0)


def test_matrix_step_negative_raises():
    with pytest.raises(ValueError, match="step.*positive"):
        ui.matrix([[1]], step=-0.5)


def test_matrix_step_per_element_zero_raises():
    with pytest.raises(ValueError, match="step.*positive"):
        ui.matrix([[1, 2]], step=[[1, 0]])


def test_matrix_3d_value_raises():
    """Test that 3D input produces a clear error, not a confusing TypeError."""

    class Fake3D:
        def tolist(self):
            return [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]

    with pytest.raises(ValueError, match="2D"):
        ui.matrix(Fake3D())


def test_matrix_3d_param_raises():
    """Test that 3D input for a broadcast param raises clearly."""

    class Fake3D:
        def tolist(self):
            return [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]

    with pytest.raises(ValueError, match="2D"):
        ui.matrix([[1, 2], [3, 4]], min_value=Fake3D())


def test_matrix_symmetric_asymmetric_data_raises():
    with pytest.raises(ValueError, match="not symmetric"):
        ui.matrix([[1, 2], [999, 1]], symmetric=True)


def test_matrix_symmetric_valid():
    m = ui.matrix([[1, 0.5], [0.5, 1]], symmetric=True)
    assert m.value == [[1.0, 0.5], [0.5, 1.0]]


def test_matrix_precision_default_integers():
    """Integer data with default step=1 -> precision 0."""
    m = ui.matrix([[1, 2], [3, 4]])
    assert m._component_args["precision"] == 0


def test_matrix_precision_default_float_step():
    """Float step should drive inferred precision."""
    m = ui.matrix([[0, 0]], step=0.25)
    assert m._component_args["precision"] == 2


def test_matrix_precision_default_float_data():
    """Float data values should drive inferred precision."""
    m = ui.matrix([[1.5, 2.33]])
    assert m._component_args["precision"] == 2


def test_matrix_precision_explicit():
    """Explicit precision should override auto-inference."""
    m = ui.matrix([[1, 2]], precision=5)
    assert m._component_args["precision"] == 5


def test_matrix_precision_scientific_small():
    """Scientific notation: 1e-8 needs 0 mantissa places, not 8."""
    m = ui.matrix([[1e-8]], scientific=True)
    assert m._component_args["precision"] == 0


def test_matrix_precision_scientific_mixed():
    """Scientific notation: 0.00153 -> 1.53e-3 -> 2 mantissa places."""
    m = ui.matrix([[0.00153, 1e-8]], scientific=True)
    assert m._component_args["precision"] == 2


def test_matrix_precision_scientific_step():
    """Scientific notation: step mantissa drives precision."""
    m = ui.matrix([[0]], step=2.5e-3, scientific=True)
    # 2.5e-3 -> mantissa 2.5 -> 1 decimal place
    assert m._component_args["precision"] == 1


# =========================================================================
# 1D (vector) tests
# =========================================================================


def test_matrix_1d_column():
    """1D input creates a column vector; value is a flat list."""
    m = ui.matrix([1, 2, 3])
    assert m.value == [1, 2, 3]


def test_matrix_1d_single_element():
    m = ui.matrix([5])
    assert m.value == [5]


def test_matrix_1d_scalar_bounds():
    m = ui.matrix([0, 0, 0], min_value=-10, max_value=10, step=0.5)
    assert m.value == [0, 0, 0]


def test_matrix_1d_per_element_bounds():
    m = ui.matrix([1, 2, 3], min_value=[0, 1, 2], max_value=[5, 6, 7])
    assert m.value == [1, 2, 3]


def test_matrix_1d_per_element_step():
    m = ui.matrix([0, 0], step=[0.1, 0.5])
    assert m.value == [0, 0]


def test_matrix_1d_per_element_disabled():
    m = ui.matrix([1, 2, 3], disabled=[True, False, True])
    assert m.value == [1, 2, 3]


def test_matrix_1d_scalar_disabled():
    m = ui.matrix([1, 2], disabled=True)
    assert m.value == [1, 2]


def test_matrix_1d_row_labels():
    """For column vector, row_labels are set."""
    m = ui.matrix([1, 2, 3], row_labels=["x", "y", "z"])
    assert m._component_args["row-labels"] == ["x", "y", "z"]
    assert m._component_args["column-labels"] is None


def test_matrix_1d_convert_value():
    """_convert_value flattens 2D back to 1D for column vector."""
    m = ui.matrix([1, 2, 3])
    result = m._convert_value([[10], [20], [30]])
    assert result == [10, 20, 30]


def test_matrix_1d_update():
    m = ui.matrix([1, 2, 3])
    m._update([[10], [20], [30]])
    assert m.value == [10, 20, 30]


def test_matrix_1d_scientific():
    m = ui.matrix([0.001, 1000], scientific=True, precision=2)
    assert m.value == [0.001, 1000]


def test_matrix_1d_debounce():
    m = ui.matrix([1, 2], debounce=True)
    assert m._component_args["debounce"] is True


def test_matrix_1d_precision_explicit():
    m = ui.matrix([1.0], precision=5)
    assert m._component_args["precision"] == 5


def test_matrix_1d_precision_default_integers():
    """Integer data with default step=1 -> precision 0."""
    m = ui.matrix([1, 2, 3])
    assert m._component_args["precision"] == 0


def test_matrix_1d_precision_default_float_step():
    """Float step should drive inferred precision."""
    m = ui.matrix([0, 0], step=0.1)
    assert m._component_args["precision"] == 1


def test_matrix_1d_precision_default_float_data():
    """Float data values should drive inferred precision."""
    m = ui.matrix([1.5, 2.333])
    assert m._component_args["precision"] == 3


def test_matrix_1d_precision_scientific():
    """Scientific notation: 1e-8 needs 0 mantissa places, not 8."""
    m = ui.matrix([1e-8, 0.00153], scientific=True)
    assert m._component_args["precision"] == 2


def test_matrix_1d_label():
    m = ui.matrix([1, 2], label="test label")
    assert m.value == [1, 2]


def test_matrix_1d_numpy_array():
    """Test that 1D array-like objects with .tolist() are accepted."""

    class FakeArray1D:
        def tolist(self):
            return [1.0, 2.0, 3.0]

    m = ui.matrix(FakeArray1D())
    assert m.value == [1.0, 2.0, 3.0]


def test_matrix_1d_numpy_bounds():
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

    m = ui.matrix(FakeArray1D(), min_value=FakeMins(), max_value=FakeMaxs())
    assert m.value == [0.0, 0.0]


# --- 1D validation error tests ---


def test_matrix_1d_empty_raises():
    with pytest.raises(ValueError, match="non-empty"):
        ui.matrix([])


def test_matrix_1d_min_ge_max_raises():
    with pytest.raises(ValueError, match="less than"):
        ui.matrix([5], min_value=10, max_value=5)


def test_matrix_1d_value_below_min_raises():
    with pytest.raises(ValueError, match="less than min_value"):
        ui.matrix([0], min_value=1)


def test_matrix_1d_value_above_max_raises():
    with pytest.raises(ValueError, match="greater than max_value"):
        ui.matrix([10], max_value=5)


def test_matrix_1d_step_zero_raises():
    with pytest.raises(ValueError, match="step.*positive"):
        ui.matrix([1], step=0)


def test_matrix_1d_step_negative_raises():
    with pytest.raises(ValueError, match="step.*positive"):
        ui.matrix([1], step=-0.5)


def test_matrix_1d_bounds_length_mismatch_raises():
    with pytest.raises(ValueError, match="rows"):
        ui.matrix([1, 2], min_value=[0, 0, 0])


def test_matrix_1d_negative_precision_raises():
    with pytest.raises(ValueError, match="precision"):
        ui.matrix([1], precision=-1)


def test_matrix_1d_2d_param_raises():
    """1D params that are actually 2D should be rejected."""
    with pytest.raises(ValueError, match="1D"):
        ui.matrix([1, 2], step=[[0.1, 0.2], [0.3, 0.4]])


def test_matrix_1d_symmetric_raises():
    """symmetric=True with 1D input should raise."""
    with pytest.raises(ValueError, match="symmetric.*not supported.*1D"):
        ui.matrix([1, 2], symmetric=True)


def test_matrix_1d_uses_matrix_plugin():
    """1D input should use the marimo-matrix frontend component."""
    m = ui.matrix([1, 2])
    assert m._name == "marimo-matrix"
