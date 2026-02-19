from __future__ import annotations

import pytest

from marimo._plugins import ui


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


# --- Validation error tests ---


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
    """Integer data with default step=1 → precision 0."""
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
    """Scientific notation: 0.00153 → 1.53e-3 → 2 mantissa places."""
    m = ui.matrix([[0.00153, 1e-8]], scientific=True)
    assert m._component_args["precision"] == 2


def test_matrix_precision_scientific_step():
    """Scientific notation: step mantissa drives precision."""
    m = ui.matrix([[0]], step=2.5e-3, scientific=True)
    # 2.5e-3 → mantissa 2.5 → 1 decimal place
    assert m._component_args["precision"] == 1


# --- NumPy return type tests ---


def test_matrix_numpy_value_returns_ndarray():
    """When constructed from np.ndarray, .value returns np.ndarray."""
    import numpy as np

    m = ui.matrix(np.eye(2))
    assert isinstance(m.value, np.ndarray)
    np.testing.assert_array_equal(m.value, np.eye(2))


def test_matrix_numpy_convert_value_returns_ndarray():
    """_convert_value returns ndarray when constructed from ndarray."""
    import numpy as np

    m = ui.matrix(np.eye(2))
    result = m._convert_value([[5, 6], [7, 8]])
    assert isinstance(result, np.ndarray)
    np.testing.assert_array_equal(result, np.array([[5, 6], [7, 8]]))


def test_matrix_list_value_returns_list():
    """When constructed from a list, .value returns a list."""
    m = ui.matrix([[1, 2], [3, 4]])
    assert isinstance(m.value, list)
    assert m.value == [[1, 2], [3, 4]]


def test_matrix_numpy_update_returns_ndarray():
    """After _update, value is still ndarray when constructed from ndarray."""
    import numpy as np

    m = ui.matrix(np.eye(2))
    m._update([[10, 20], [30, 40]])
    assert isinstance(m.value, np.ndarray)
    np.testing.assert_array_equal(m.value, np.array([[10, 20], [30, 40]]))
