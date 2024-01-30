# Copyright 2024 Marimo. All rights reserved.
import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.dataframes.handlers import (
    TransformsContainer,
    apply_transforms,
)
from marimo._plugins.ui._impl.dataframes.transforms import (
    AggregateTransform,
    ColumnConversionTransform,
    Condition,
    FilterRowsTransform,
    GroupByTransform,
    RenameColumnTransform,
    SampleRowsTransform,
    SelectColumnsTransform,
    ShuffleRowsTransform,
    SortColumnTransform,
    Transform,
    Transformations,
    TransformType,
)

HAS_DEPS = DependencyManager.has_pandas()

if HAS_DEPS:
    import pandas as pd


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestHandlers:
    @staticmethod
    def apply(df: "pd.DataFrame", transform: Transform) -> "pd.DataFrame":
        return apply_transforms(df, Transformations(transforms=[transform]))

    @staticmethod
    def test_handle_column_conversion() -> None:
        # 1 string to int
        df = pd.DataFrame({"A": ["1", "2", "3"]})
        transform = ColumnConversionTransform(
            type=TransformType.COLUMN_CONVERSION,
            column_id="A",
            data_type="int",
            errors="raise",
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].dtype == "int"
        # 2 float to string
        df = pd.DataFrame({"A": [1.1, 2.2, 3.3]})
        transform = ColumnConversionTransform(
            type=TransformType.COLUMN_CONVERSION,
            column_id="A",
            data_type="str",
            errors="raise",
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].dtype == "object"
        assert result["A"].tolist() == ["1.1", "2.2", "3.3"]
        # 3 with errors
        df = pd.DataFrame({"A": ["1", "2", "3", "a"]})
        transform = ColumnConversionTransform(
            type=TransformType.COLUMN_CONVERSION,
            column_id="A",
            data_type="int",
            errors="ignore",
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].dtype == "object"
        assert result["A"].tolist() == ["1", "2", "3", "a"]

    @staticmethod
    def test_handle_rename_column() -> None:
        df = pd.DataFrame({"A": [1, 2, 3]})
        transform = RenameColumnTransform(
            type=TransformType.RENAME_COLUMN, column_id="A", new_column_id="B"
        )
        result = TestHandlers.apply(df, transform)
        assert "B" in result.columns
        assert "A" not in result.columns

        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = RenameColumnTransform(
            type=TransformType.RENAME_COLUMN, column_id="B", new_column_id="C"
        )
        result = TestHandlers.apply(df, transform)
        assert "C" in result.columns
        assert "B" not in result.columns

    @staticmethod
    def test_handle_sort_column() -> None:
        df = pd.DataFrame({"A": [3, 2, 1]})
        transform = SortColumnTransform(
            type=TransformType.SORT_COLUMN,
            column_id="A",
            ascending=True,
            na_position="last",
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].tolist() == [1, 2, 3]

        df = pd.DataFrame({"A": [3, 2, 1], "B": [1, 3, 2]})
        transform = SortColumnTransform(
            type=TransformType.SORT_COLUMN,
            column_id="B",
            ascending=False,
            na_position="last",
        )
        result = TestHandlers.apply(df, transform)
        assert result["B"].tolist() == [3, 2, 1]

    @staticmethod
    def test_handle_filter_rows_1() -> None:
        df = pd.DataFrame({"A": [1, 2, 3]})
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator=">=", value=2)],
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].tolist() == [2, 3]

    @staticmethod
    def test_handle_filter_rows_2() -> None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[Condition(column_id="B", operator="!=", value=5)],
        )
        result = TestHandlers.apply(df, transform)
        assert result["B"].tolist() == [5]

    @staticmethod
    def test_handle_filter_rows_3() -> None:
        df = pd.DataFrame({"A": [1, 2, 3, 4, 5]})
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator="<", value=4)],
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].tolist() == [1, 2, 3]

    @staticmethod
    def test_handle_filter_rows_4() -> None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[Condition(column_id="A", operator="==", value=2)],
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].tolist() == [1, 3]

    @staticmethod
    def test_handle_filter_rows_5() -> None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="B", operator=">=", value=5)],
        )
        result = TestHandlers.apply(df, transform)
        assert result["B"].tolist() == [5, 6]

    @staticmethod
    def test_handle_filter_rows_6() -> None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[Condition(column_id="B", operator="<", value=6)],
        )
        result = TestHandlers.apply(df, transform)
        assert result["B"].tolist() == [6]

    @staticmethod
    def test_handle_filter_rows_multiple_conditions_1() -> None:
        df = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]})
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(column_id="A", operator=">=", value=3),
                Condition(column_id="B", operator="<=", value=3),
            ],
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].tolist() == [3, 4, 5]
        assert result["B"].tolist() == [3, 2, 1]

    @staticmethod
    def test_handle_filter_rows_multiple_conditions_2() -> None:
        df = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]})
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[
                Condition(column_id="A", operator="==", value=2),
                Condition(column_id="B", operator="==", value=4),
            ],
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].tolist() == [1, 3, 4, 5]
        assert result["B"].tolist() == [5, 3, 2, 1]

    @staticmethod
    def test_handle_filter_rows_boolean() -> None:
        df = pd.DataFrame({"A": [True, False, True, False]})
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator="is_true")],
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].tolist() == [True, True]

        df = pd.DataFrame({"A": [True, False, True, False]})
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[Condition(column_id="A", operator="is_false")],
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"].tolist() == [True, True]

    @staticmethod
    def test_handle_group_by() -> None:
        df = pd.DataFrame({"A": ["foo", "foo", "bar"], "B": [1, 2, 3]})
        transform = GroupByTransform(
            type=TransformType.GROUP_BY,
            column_ids=["A"],
            drop_na=False,
            aggregation="sum",
        )
        result = TestHandlers.apply(df, transform)
        assert result["B"].tolist() == [3, 3]

        df = pd.DataFrame(
            {"A": ["foo", "foo", "bar", "bar"], "B": [1, 2, 3, 4]}
        )
        transform = GroupByTransform(
            type=TransformType.GROUP_BY,
            column_ids=["A"],
            drop_na=False,
            aggregation="mean",
        )
        result = TestHandlers.apply(df, transform)
        assert set(result["B"].tolist()) == set([1.5, 3.5])

    @staticmethod
    def test_handle_aggregate() -> None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = AggregateTransform(
            type=TransformType.AGGREGATE,
            column_ids=["A", "B"],
            aggregations=["sum"],
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"]["sum"] == 6
        assert result["B"]["sum"] == 15

        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = AggregateTransform(
            type=TransformType.AGGREGATE,
            column_ids=["A", "B"],
            aggregations=["min", "max"],
        )
        result = TestHandlers.apply(df, transform)
        assert result["A"]["min"] == 1
        assert result["A"]["max"] == 3
        assert result["B"]["min"] == 4
        assert result["B"]["max"] == 6

    @staticmethod
    def test_handle_select_columns() -> None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = SelectColumnsTransform(
            type=TransformType.SELECT_COLUMNS, column_ids=["A"]
        )
        result = TestHandlers.apply(df, transform)
        assert "A" in result.columns
        assert "B" not in result.columns

        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = SelectColumnsTransform(
            type=TransformType.SELECT_COLUMNS, column_ids=["B"]
        )
        result = TestHandlers.apply(df, transform)
        assert "B" in result.columns
        assert "A" not in result.columns

        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = SelectColumnsTransform(
            type=TransformType.SELECT_COLUMNS, column_ids=["A", "B"]
        )
        result = TestHandlers.apply(df, transform)
        assert "A" in result.columns
        assert "B" in result.columns

    @staticmethod
    def test_shuffle_rows() -> None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = ShuffleRowsTransform(
            type=TransformType.SHUFFLE_ROWS, seed=42
        )
        result = TestHandlers.apply(df, transform)
        assert len(result) == 3
        assert "A" in result.columns
        assert "B" in result.columns

    @staticmethod
    def test_sample_rows() -> None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        transform = SampleRowsTransform(
            type=TransformType.SAMPLE_ROWS, n=2, seed=42, replace=False
        )
        result = TestHandlers.apply(df, transform)
        assert len(result) == 2
        assert "A" in result.columns
        assert "B" in result.columns

    @staticmethod
    def test_transforms_container() -> None:
        # Create a sample dataframe
        df = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]})
        # Create a TransformsContainer object
        container = TransformsContainer(df)

        # Define some transformations
        sort_transform = SortColumnTransform(
            type=TransformType.SORT_COLUMN,
            column_id="B",
            ascending=False,
            na_position="last",
        )
        filter_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator=">=", value=2)],
        )
        transformations = Transformations([sort_transform, filter_transform])
        # Verify the next transformation
        assert container._is_superset(transformations) is False
        assert (
            container._get_next_transformations(transformations)
            == transformations
        )

        # Apply the transformations
        result = container.apply(transformations)

        # Get the transformed dataframe
        # Check that the transformations were applied correctly
        assert result["A"].tolist() == [2, 3, 4, 5]
        assert result["B"].tolist() == [4, 3, 2, 1]

        # Reapply transforms by adding a new one
        filter_again_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[Condition(column_id="B", operator="==", value=4)],
        )
        transformations = Transformations(
            [sort_transform, filter_transform, filter_again_transform]
        )
        # Verify the next transformation
        assert container._is_superset(transformations) is True
        assert container._get_next_transformations(
            transformations
        ) == Transformations([filter_again_transform])
        result = container.apply(
            transformations,
        )
        # Check that the transformations were applied correctly
        assert result["A"].tolist() == [3, 4, 5]
        assert result["B"].tolist() == [3, 2, 1]

        transformations = Transformations([sort_transform, filter_transform])
        # Verify the next transformation
        assert container._is_superset(transformations) is False
        assert (
            container._get_next_transformations(transformations)
            == transformations
        )
        # Reapply by removing the last transform
        result = container.apply(
            transformations,
        )
        # Check that the transformations were applied correctly
        assert result["A"].tolist() == [2, 3, 4, 5]
        assert result["B"].tolist() == [4, 3, 2, 1]
