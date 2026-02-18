from __future__ import annotations

import pytest

from marimo._plugins import ui


def test_matrix_basic():
    m = ui.matrix([[1, 2], [3, 4]])
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
    with pytest.raises(ValueError, match="same length"):
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
