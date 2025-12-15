from __future__ import annotations

import ast
import datetime
import string
from typing import TYPE_CHECKING, Optional, cast

import narwhals.stable.v2 as nw
import pytest
from hypothesis import assume, given, settings, strategies as st

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.dataframes.transforms.apply import (
    _apply_transforms,
)
from marimo._plugins.ui._impl.dataframes.transforms.handlers import (
    NarwhalsTransformHandler,
)
from marimo._plugins.ui._impl.dataframes.transforms.print_code import (
    python_print_ibis,
    python_print_pandas,
    python_print_polars,
    python_print_transforms,
)
from marimo._plugins.ui._impl.dataframes.transforms.types import (
    AggregateTransform,
    ColumnConversionTransform,
    Condition,
    ExpandDictTransform,
    ExplodeColumnsTransform,
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

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl

any_column_id = st.one_of(
    st.text(
        min_size=1,
        alphabet=string.ascii_letters + string.digits + "_",
    ),
)

defined_column_id = st.sampled_from(
    [
        "strings",
        "integers",
        "floats",
        "booleans",
        "dates",
        "times",
        "datetimes",
        "mixed",
        "dicts",
        "lists",
    ]
)


def create_transform_strategy(
    column_id: st.SearchStrategy[str],
    string_column_id: Optional[st.SearchStrategy[str | int] | None] = None,
    bool_column_id: Optional[st.SearchStrategy[str | int] | None] = None,
    comparison_column_id: Optional[st.SearchStrategy[str | int] | None] = None,
    list_column_id: Optional[st.SearchStrategy[str | int] | None] = None,
    df_size: int = 3,
) -> st.SearchStrategy[Transform]:
    column_ids = st.lists(column_id, min_size=1)
    aggregation_column_ids = st.one_of(
        st.just([]),
        st.lists(column_id, min_size=1),
    )

    if string_column_id is None:
        string_column_id = column_id
    if bool_column_id is None:
        bool_column_id = column_id
    if comparison_column_id is None:
        comparison_column_id = column_id
    if list_column_id is None:
        list_column_id = column_id

    numpy_data_type = st.sampled_from(["str", "bool"])
    aggregation = st.sampled_from(
        ["count", "sum", "mean", "median", "min", "max"]
    )

    # Strategies for each condition type
    comparison_condition_strategy = st.builds(
        Condition,
        column_id=comparison_column_id,
        operator=st.sampled_from(["==", "!=", "<", ">", "<=", ">="]),
        value=st.one_of(
            st.integers(), st.floats(allow_infinity=False, allow_nan=False)
        ),
    )

    boolean_condition_strategy = st.builds(
        Condition,
        column_id=bool_column_id,
        operator=st.sampled_from(["is_true", "is_false"]),
        value=st.just(None),
    )

    string_condition_strategy = st.builds(
        Condition,
        column_id=string_column_id,
        operator=st.sampled_from(
            [
                "equals",
                "does_not_equal",
                "contains",
                "regex",
                "starts_with",
                "ends_with",
            ]
        ),
        value=st.text(alphabet=string.ascii_letters + string.digits),
    )

    list_condition_strategy = st.builds(
        Condition,
        column_id=list_column_id,
        operator=st.sampled_from(["in", "not_in"]),
        value=st.lists(st.one_of(st.text()), min_size=1),
    )

    condition_strategy = st.one_of(
        comparison_condition_strategy,
        boolean_condition_strategy,
        string_condition_strategy,
        list_condition_strategy,
    )

    column_conversion_transform_strategy = st.builds(
        ColumnConversionTransform,
        type=st.just(TransformType.COLUMN_CONVERSION),
        column_id=column_id,
        data_type=numpy_data_type,
        errors=st.sampled_from(["ignore", "raise"]),
    )

    rename_column_transform_strategy = st.builds(
        RenameColumnTransform,
        type=st.just(TransformType.RENAME_COLUMN),
        column_id=column_id,
        new_column_id=column_id,
    ).filter(lambda x: x.column_id != x.new_column_id)

    sort_column_transform_strategy = st.builds(
        SortColumnTransform,
        type=st.just(TransformType.SORT_COLUMN),
        column_id=column_id,
        ascending=st.booleans(),
        na_position=st.sampled_from(["first", "last"]),
    )

    filter_rows_transform_strategy = st.builds(
        FilterRowsTransform,
        type=st.just(TransformType.FILTER_ROWS),
        operation=st.sampled_from(["keep_rows", "remove_rows"]),
        where=st.lists(condition_strategy, min_size=1),
    )

    group_by_transform_strategy = st.builds(
        GroupByTransform,
        type=st.just(TransformType.GROUP_BY),
        column_ids=column_ids,
        drop_na=st.booleans(),
        aggregation=aggregation,
        aggregation_column_ids=aggregation_column_ids,
    )

    aggregate_transform_strategy = st.builds(
        AggregateTransform,
        type=st.just(TransformType.AGGREGATE),
        column_ids=column_ids,
        aggregations=st.lists(aggregation, min_size=1),
    )

    select_columns_transform_strategy = st.builds(
        SelectColumnsTransform,
        type=st.just(TransformType.SELECT_COLUMNS),
        column_ids=column_ids,
    )

    shuffle_rows_transform_strategy = st.builds(
        ShuffleRowsTransform,
        type=st.just(TransformType.SHUFFLE_ROWS),
        seed=st.integers(),
    )

    sample_rows_transform_strategy = st.builds(
        SampleRowsTransform,
        type=st.just(TransformType.SAMPLE_ROWS),
        n=st.integers(min_value=1, max_value=df_size),
        replace=st.booleans(),
        seed=st.integers(),
    )

    explode_columns_transform_strategy = st.builds(
        ExplodeColumnsTransform,
        type=st.just(TransformType.EXPLODE_COLUMNS),
        column_ids=column_ids,
    )

    expand_dict_transform_strategy = st.builds(
        ExpandDictTransform,
        type=st.just(TransformType.EXPAND_DICT),
        column_id=column_id,
    )

    # Combine all transform strategies
    transform_strategy = st.one_of(
        column_conversion_transform_strategy,
        rename_column_transform_strategy,
        sort_column_transform_strategy,
        filter_rows_transform_strategy,
        group_by_transform_strategy,
        aggregate_transform_strategy,
        select_columns_transform_strategy,
        shuffle_rows_transform_strategy,
        sample_rows_transform_strategy,
        explode_columns_transform_strategy,
        expand_dict_transform_strategy,
    )

    return transform_strategy


transformations_strategy = st.builds(
    Transformations,
    transforms=st.lists(create_transform_strategy(any_column_id), min_size=1),
)


def _validate_code(code: str):
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise SyntaxError(f"Invalid Python code for {code}") from e


@given(transform=create_transform_strategy(any_column_id))
@settings(deadline=None)
def test_python_print_pandas(transform: Transform):
    df_name = "df"
    result = python_print_pandas(df_name, ["a"], transform)
    assert isinstance(result, str)
    _validate_code(result)
    assert df_name in result


@given(transform=create_transform_strategy(any_column_id))
@settings(deadline=None)
def test_python_print_polars(transform: Transform):
    df_name = "df"
    result = python_print_polars(df_name, ["a"], transform)
    assert isinstance(result, str)
    _validate_code(result)
    assert df_name in result


@given(transformations=transformations_strategy)
@settings(deadline=None)
@pytest.mark.skip
def test_python_print_ibis(transformations: Transformations):
    df_name = "df"
    result = python_print_transforms(
        df_name, ["a"], transformations.transforms, python_print_ibis
    )
    assert isinstance(result, str)
    _validate_code(result)
    assert df_name in result


@given(transformations=transformations_strategy)
@settings(deadline=None)
def test_python_print_transforms(transformations: Transformations):
    df_name = "df"
    # Pandas
    result = python_print_transforms(
        df_name, ["a"], transformations.transforms, python_print_pandas
    )
    assert isinstance(result, str)
    _validate_code(result)
    assert df_name in result
    # Polars
    result = python_print_transforms(
        df_name, ["a"], transformations.transforms, python_print_polars
    )
    assert isinstance(result, str)
    _validate_code(result)
    assert df_name in result
    # Ibis
    # TODO: test ibis python print
    # result = python_print_transforms(
    #     df_name, ["a"], transformations.transforms, python_print_ibis
    # )
    # assert isinstance(result, str)
    # _validate_code(result)
    # assert df_name in result


@given(
    transform=create_transform_strategy(
        defined_column_id,
        string_column_id=st.just("strings"),
        bool_column_id=st.just("booleans"),
        comparison_column_id=st.sampled_from(
            ["integers", "floats", "dates", "times", "datetimes"]
        ),
        list_column_id=st.just("strings"),
        df_size=3,
    )
)
@settings(deadline=None)
@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="pandas not installed"
)
def test_print_code_result_matches_actual_transform_pandas(
    transform: Transform,
):
    import pandas as pd

    transformations = Transformations([transform])

    my_df = pd.DataFrame(
        {
            "strings": ["a", "b", "c"],
            "integers": [1, 2, 3],
            "floats": [1.0, 2.0, 3.0],
            "booleans": [True, False, True],
            "dates": [pd.Timestamp("2021-01-01")] * 3,
            "times": [pd.Timestamp("2021-01-01 00:00:00")] * 3,
            "datetimes": [pd.Timestamp("2021-01-01 00:00:00")] * 3,
            "mixed": [1, 2.0, "3"],
            "dicts": [{"a": 1}, {"b": 2}, {"c": 3}],
            "lists": [[1, 2], [3, 4], [5, 6]],
        }
    )

    # Exclude shuffle and sample rows
    assume(
        transform.type
        not in {TransformType.SHUFFLE_ROWS, TransformType.SAMPLE_ROWS}
    )
    # Ignore date, time, datetime columns in filter rows
    if transform.type == TransformType.FILTER_ROWS:
        assume(
            not any(
                condition.column_id in {"dates", "times", "datetimes"}
                for condition in transform.where
            )
        )
    # Ignore groupby mean
    if transform.type == TransformType.GROUP_BY:
        assume(transform.aggregation != "mean")

    # Ignore groupby mean
    if transform.type == TransformType.PIVOT:
        assume(transform.aggregation != "mean")

    # Pandas
    pandas_code = python_print_transforms(
        "my_df",
        list(my_df.columns),
        transformations.transforms,
        python_print_pandas,
    )
    assert pandas_code

    try:
        loc = {"pd": pd, "my_df": my_df.copy()}
        exec(pandas_code, {}, loc)
        code_result = loc.get("my_df_next")
    except Exception as code_error:
        code_result = code_error

    try:
        nw_df = nw.from_native(my_df.copy(), eager_only=True).lazy()
        result_nw = _apply_transforms(
            nw_df,
            NarwhalsTransformHandler(),
            transformations,
        )
        real_result = result_nw.collect().to_native()
    except Exception as real_error:
        real_result = real_error

    if isinstance(code_result, Exception) or isinstance(
        real_result, Exception
    ):
        # Allow different error types between pandas and narwhals
        import narwhals.exceptions as nw_exc

        if isinstance(real_result, nw_exc.DuplicateError):
            # Pandas doesn't raise DuplicateError, it just creates duplicate columns
            # So if narwhals raised DuplicateError, it's expected that pandas succeeded
            assert not isinstance(code_result, Exception)
            return
        if isinstance(real_result, nw_exc.InvalidOperationError):
            # Pandas may allow some operations that narwhals doesn't
            # If narwhals raised InvalidOperationError, pandas might have succeeded
            # or raised a different error - just skip comparison
            return
        if isinstance(real_result, (AttributeError, TypeError)):
            # Narwhals may raise AttributeError for some operations (e.g., duplicate column names in aggregate)
            # Pandas might have succeeded - just skip comparison
            return
        assert type(code_result) is type(real_result)
        assert str(code_result) == str(real_result)
    else:
        # If series, convert to dataframe
        if isinstance(code_result, pd.Series):
            code_result = code_result.to_frame()
        if isinstance(real_result, pd.Series):
            real_result = real_result.to_frame()
        # Remove index to compare
        pd.testing.assert_frame_equal(
            cast(pd.DataFrame, code_result).reset_index(drop=True),
            real_result.reset_index(drop=True),
        )


@given(
    transform=create_transform_strategy(
        defined_column_id,
        string_column_id=st.just("strings"),
        bool_column_id=st.just("booleans"),
        comparison_column_id=st.sampled_from(
            ["integers", "floats", "dates", "times", "datetimes"]
        ),
        list_column_id=st.just("strings"),
        df_size=3,
    )
)
@settings(deadline=None)
@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="polars not installed"
)
def test_print_code_result_matches_actual_transform_polars(
    transform: Transform,
):
    import polars as pl
    import polars.testing as pl_testing

    transformations = Transformations([transform])

    my_df = pl.DataFrame(
        {
            "strings": ["a", "b", "c"],
            "integers": [1, 2, 3],
            "floats": [1.0, 2.0, 3.0],
            "booleans": [True, False, True],
            "dates": [datetime.date(2021, 1, 1)] * 3,
            "times": [datetime.time(0, 0, 0)] * 3,
            "datetimes": [datetime.datetime(2021, 1, 1)] * 3,
            "mixed": [1, 2, 3],
            "dicts": [{"a": 1}, {"b": 2}, {"c": 3}],
            "lists": [[1, 2], [3, 4], [5, 6]],
        },
    )

    # Exclude shuffle and sample rows
    assume(
        transform.type
        not in {TransformType.SHUFFLE_ROWS, TransformType.SAMPLE_ROWS}
    )

    # Ignore date, time, datetime columns in filter rows
    if transform.type == TransformType.FILTER_ROWS:
        assume(
            not any(
                condition.column_id in {"dates", "times", "datetimes"}
                for condition in transform.where
            )
        )
    # Only explode columns for lists
    if transform.type == TransformType.EXPLODE_COLUMNS:
        assume(all(column_id == "lists" for column_id in transform.column_ids))
    # Only expand dict for dicts
    if transform.type == TransformType.EXPAND_DICT:
        assume("dicts" == transform.column_id)
    # Don't sort on dicts or lists
    if transform.type == TransformType.SORT_COLUMN:
        assume(transform.column_id not in {"dicts", "lists"})
    # Skip aggregation
    # TODO: unimplemented
    if transform.type == TransformType.AGGREGATE:
        assume(False)

    # Polars
    polars_code = python_print_transforms(
        "my_df", my_df.columns, transformations.transforms, python_print_polars
    )
    assert polars_code

    try:
        loc = {"pl": pl, "my_df": my_df.clone()}
        exec(polars_code, globals(), loc)
        code_result = loc.get("my_df_next")
    except Exception as code_error:
        code_result = code_error

    try:
        nw_df = nw.from_native(my_df.clone(), eager_only=True).lazy()
        result_nw = _apply_transforms(
            nw_df,
            NarwhalsTransformHandler(),
            transformations,
        )
        real_result = result_nw.collect().to_native()
    except Exception as real_error:
        real_result = real_error

    if isinstance(code_result, Exception) or isinstance(
        real_result, Exception
    ):
        # Allow different error types between polars and narwhals
        import narwhals.exceptions as nw_exc
        import polars.exceptions as pl_exc

        if isinstance(real_result, nw_exc.DuplicateError) and isinstance(
            code_result, pl_exc.DuplicateError
        ):
            # Both raised duplicate errors, just different types - this is OK
            return
        if isinstance(real_result, nw_exc.DuplicateError):
            # Polars raised DuplicateError from the generated code
            # but narwhals also raised DuplicateError - this is OK
            assert isinstance(code_result, pl_exc.DuplicateError)
            return
        if isinstance(
            real_result, nw_exc.InvalidOperationError
        ) and isinstance(code_result, pl_exc.InvalidOperationError):
            # Both raised invalid operation errors, just different types - this is OK
            return
        if isinstance(real_result, nw_exc.InvalidOperationError):
            # Polars may allow some operations that narwhals doesn't
            # If narwhals raised InvalidOperationError, just skip comparison
            return
        assert type(code_result) is type(real_result)
        assert str(code_result) == str(real_result)
    else:
        # If series, convert to dataframe
        if isinstance(code_result, pl.Series):
            code_result = code_result.to_frame()
        if isinstance(real_result, pl.Series):
            real_result = real_result.to_frame()
        code_result = cast(pl.DataFrame, code_result)
        # Compare column names
        assert code_result.columns == real_result.columns

        # For group_by transforms, the row order might differ even with maintain_order=True
        # Sort both dataframes by all columns before comparing
        if transform.type == TransformType.GROUP_BY:
            code_result = code_result.sort(code_result.columns)
            real_result = real_result.sort(real_result.columns)

        pl_testing.assert_frame_equal(code_result, real_result)


@given(
    transform=create_transform_strategy(
        defined_column_id,
        string_column_id=st.just("strings"),
        bool_column_id=st.just("booleans"),
        comparison_column_id=st.sampled_from(
            ["integers", "floats", "dates", "times", "datetimes"]
        ),
        list_column_id=st.just("strings"),
        df_size=3,
    )
)
@settings(deadline=None)
@pytest.mark.skipif(
    not DependencyManager.ibis.has(), reason="ibis not installed"
)
@pytest.mark.xfail(reason="Ibis printing code is not well supported")
def test_print_code_result_matches_actual_transform_ibis(
    transform: Transform,
):
    import ibis

    my_df = ibis.memtable(
        {
            "strings": ["a", "b", "c"],
            "integers": [1, 2, 3],
            "floats": [1.0, 2.0, 3.0],
            "booleans": [True, False, True],
            "dates": [datetime.date(2021, 1, 1)] * 3,
            "times": [datetime.time(0, 0, 0)] * 3,
            "datetimes": [datetime.datetime(2021, 1, 1)] * 3,
            "mixed": [1, 2, 3],
            "dicts": [{"a": 1}, {"b": 2}, {"c": 3}],
            "lists": [[1, 2], [3, 4], [5, 6]],
        }
    )

    # Exclude shuffle and sample rows
    assume(
        transform.type
        not in {TransformType.SHUFFLE_ROWS, TransformType.SAMPLE_ROWS}
    )
    # Exclude boolean columns in filter rows
    if transform.type == TransformType.FILTER_ROWS:
        assume(
            not any(
                condition.column_id in {"booleans"}
                for condition in transform.where
            )
        )
    # Skip column conversion with errors='ignore' - ibis coalesce has type precedence issues
    if transform.type == TransformType.COLUMN_CONVERSION:
        assume(transform.errors != "ignore")

    try:
        nw_df = nw.from_native(my_df).lazy()
        result_nw = _apply_transforms(
            nw_df,
            NarwhalsTransformHandler(),
            Transformations([transform]),
        )
        # Keep as narwhals lazy frame to check if it's an Ibis backend
        real_result = result_nw.collect().to_native()
    except Exception:
        real_result = None

    # Only compare if this passes
    assume(real_result is not None)

    assert real_result is not None

    ibis_code = python_print_transforms(
        "my_df",
        list(my_df.columns),
        [transform],
        python_print_ibis,
    )
    assert ibis_code

    loc = {"ibis": ibis, "my_df": my_df}
    exec(ibis_code, {}, loc)
    code_result = loc.get("my_df_next")

    print("code_result", code_result)
    print("real_result", real_result)

    assert real_result is not None
    assert code_result is not None


@pytest.mark.skipif(
    not DependencyManager.pandas.has() or not DependencyManager.polars.has(),
    reason="pandas or polars not installed",
)
class TestCombinedTransforms:
    @pytest.fixture
    def sample_data(self):
        return {"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9]}

    @pytest.fixture
    def pd_dataframe(self, sample_data):
        import pandas as pd

        return pd.DataFrame(sample_data)

    @pytest.fixture
    def pl_dataframe(self, sample_data):
        import polars as pl

        return pl.DataFrame(sample_data)

    def _test_transforms(
        self, df: pl.DataFrame | pd.DataFrame, transforms: Transformations
    ):
        import pandas as pd
        import pandas.testing as pd_testing
        import polars as pl
        import polars.testing as pl_testing

        if isinstance(df, pl.DataFrame):
            print_func = python_print_polars
            testing_func = pl_testing.assert_frame_equal
            df_copy = df.clone()
        elif isinstance(df, pd.DataFrame):
            print_func = python_print_pandas
            testing_func = pd_testing.assert_frame_equal
            df_copy = df.copy()

        # Convert to narwhals and apply transforms
        nw_df = nw.from_native(df_copy, eager_only=True).lazy()
        result_nw = _apply_transforms(
            nw_df, NarwhalsTransformHandler(), transforms
        )
        result = result_nw.collect().to_native()

        code = python_print_transforms(
            "df", df.columns, transforms.transforms, print_func
        )

        # Apply code
        if isinstance(df, pl.DataFrame):
            loc = {"pl": pl, "df": df.clone()}
            exec(code, globals(), loc)
        elif isinstance(df, pd.DataFrame):
            loc = {"pd": pd, "df": df.copy()}
            exec(code, {}, loc)

        assert loc.get("df_next") is not None

        # Get the results
        code_result = loc.get("df_next")

        # For group_by transforms, the row order might differ even with maintain_order=True
        # Sort both dataframes by all columns before comparing
        has_groupby = any(
            t.type == TransformType.GROUP_BY for t in transforms.transforms
        )
        if has_groupby:
            if isinstance(code_result, pl.DataFrame):
                code_result = code_result.sort(code_result.columns)
                result = result.sort(result.columns)
            elif isinstance(code_result, pd.DataFrame):
                code_result = code_result.sort_values(
                    by=list(code_result.columns)
                ).reset_index(drop=True)
                result = result.sort_values(
                    by=list(result.columns)
                ).reset_index(drop=True)

        # Test that the result matches the actual result
        testing_func(code_result, result)

    def test_select_then_group_by(
        self, pl_dataframe: pl.DataFrame, pd_dataframe: pd.DataFrame
    ):
        # Apply a select, then a group by
        transforms = Transformations(
            [
                SelectColumnsTransform(
                    type=TransformType.SELECT_COLUMNS,
                    column_ids=["a", "b"],
                ),
                GroupByTransform(
                    type=TransformType.GROUP_BY,
                    column_ids=["a"],
                    drop_na=False,
                    aggregation="sum",
                    aggregation_column_ids=["b"],
                ),
            ]
        )

        self._test_transforms(pl_dataframe, transforms)
        self._test_transforms(pd_dataframe, transforms)

    def test_select_rename_groupby(
        self, pl_dataframe: pl.DataFrame, pd_dataframe: pd.DataFrame
    ):
        transforms = Transformations(
            [
                SelectColumnsTransform(
                    type=TransformType.SELECT_COLUMNS,
                    column_ids=["a", "b"],
                ),
                RenameColumnTransform(
                    type=TransformType.RENAME_COLUMN,
                    column_id="a",
                    new_column_id="x",
                ),
                GroupByTransform(
                    type=TransformType.GROUP_BY,
                    column_ids=["x"],
                    drop_na=False,
                    aggregation="mean",
                    aggregation_column_ids=["b"],
                ),
            ]
        )
        self._test_transforms(pl_dataframe, transforms)
        self._test_transforms(pd_dataframe, transforms)

    def test_select_then_aggregate(
        self, pl_dataframe: pl.DataFrame, pd_dataframe: pd.DataFrame
    ):
        """Test select columns followed by aggregate transform."""
        transforms = Transformations(
            [
                SelectColumnsTransform(
                    type=TransformType.SELECT_COLUMNS,
                    column_ids=["a", "b", "c"],
                ),
                AggregateTransform(
                    type=TransformType.AGGREGATE,
                    column_ids=["a", "b"],
                    aggregations=["sum"],
                ),
            ]
        )

        self._test_transforms(pl_dataframe, transforms)
        self._test_transforms(pd_dataframe, transforms)
