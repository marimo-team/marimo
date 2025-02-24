# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.dataframes.transforms.types import Condition
from marimo._plugins.ui._impl.table import SearchTableArgs, SortArgs
from marimo._plugins.ui._impl.tables.default_table import DefaultTableManager
from marimo._plugins.ui._impl.utils.dataframe import TableData
from marimo._runtime.functions import EmptyArgs
from marimo._runtime.runtime import Kernel
from marimo._utils.data_uri import from_data_uri
from tests._data.mocks import create_dataframes


@pytest.fixture
def dtm() -> None:
    return DefaultTableManager([])


def _normalize_data(data: Any) -> list[dict[str, Any]]:
    return DefaultTableManager._normalize_data(data)


def test_normalize_data(executing_kernel: Kernel) -> None:
    # unused, except for the side effect of giving the kernel an execution
    # context
    del executing_kernel

    # Create kernel and give the execution context an existing cell
    data: TableData

    # Test with list of integers
    data = [1, 2, 3]
    result = _normalize_data(data)
    assert result == [
        {"value": 1},
        {"value": 2},
        {"value": 3},
    ]

    # Test with list of strings
    data = ["a", "b", "c"]
    result = _normalize_data(data)
    assert result == [
        {"value": "a"},
        {"value": "b"},
        {"value": "c"},
    ]

    # Test with list of dictionaries
    data = [
        {"key1": "value1"},
        {"key2": "value2"},
        {"key3": "value3"},
    ]
    result = _normalize_data(data)
    assert result == [
        {"key1": "value1"},
        {"key2": "value2"},
        {"key3": "value3"},
    ]

    # Dictionary with list of integers
    data = {"key": [1, 2, 3]}
    result = _normalize_data(data)
    assert result == [
        {"key": 1},
        {"key": 2},
        {"key": 3},
    ]

    # Dictionary with tuple of integers
    data = {"key": (1, 2, 3)}
    result = _normalize_data(data)
    assert result == [
        {"key": 1},
        {"key": 2},
        {"key": 3},
    ]

    # Test with empty list
    data = []
    result = _normalize_data(data)
    assert result == []

    # Test with invalid data type
    data2: Any = "invalid data type"
    with pytest.raises(ValueError) as e:
        _normalize_data(data2)
    assert str(e.value) == "data must be a list or tuple or a dict of lists."

    # Test with invalid data structure
    data3: Any = [set([1, 2, 3])]
    with pytest.raises(ValueError) as e:
        _normalize_data(data3)
    assert (
        str(e.value) == "data must be a sequence of JSON-serializable types, "
        "or a sequence of dicts."
    )


def test_sort_1d_list_of_strings(dtm: DefaultTableManager) -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    dtm.data = _normalize_data(data)
    sorted_data = dtm.sort_values(by="value", descending=False).data
    expected_data = [
        {"value": "apple"},
        {"value": "banana"},
        {"value": "cherry"},
        {"value": "date"},
        {"value": "elderberry"},
    ]
    assert sorted_data == expected_data


def test_sort_1d_list_of_integers(dtm: DefaultTableManager) -> None:
    data = [42, 17, 23, 99, 8]
    dtm.data = _normalize_data(data)
    sorted_data = dtm.sort_values(by="value", descending=False).data
    expected_data = [
        {"value": 8},
        {"value": 17},
        {"value": 23},
        {"value": 42},
        {"value": 99},
    ]
    assert sorted_data == expected_data


def test_sort_list_of_dicts(dtm: DefaultTableManager) -> None:
    data = [
        {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
        {"name": "Bob", "age": 25, "birth_year": date(1999, 7, 14)},
        {"name": "Charlie", "age": 35, "birth_year": date(1989, 12, 1)},
        {"name": "Dave", "age": 28, "birth_year": date(1996, 3, 5)},
        {"name": "Eve", "age": 22, "birth_year": date(2002, 1, 30)},
    ]
    dtm.data = _normalize_data(data)
    sorted_data = dtm.sort_values(by="age", descending=True).data

    with pytest.raises(KeyError):
        _res = dtm.sort_values(by="missing_column", descending=True).data

    expected_data = [
        {"name": "Charlie", "age": 35, "birth_year": date(1989, 12, 1)},
        {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
        {"name": "Dave", "age": 28, "birth_year": date(1996, 3, 5)},
        {"name": "Bob", "age": 25, "birth_year": date(1999, 7, 14)},
        {"name": "Eve", "age": 22, "birth_year": date(2002, 1, 30)},
    ]
    assert sorted_data == expected_data


def test_sort_dict_of_lists(dtm: DefaultTableManager) -> None:
    data = {
        "company": [
            "Company A",
            "Company B",
            "Company C",
            "Company D",
            "Company E",
        ],
        "type": ["Tech", "Finance", "Health", "Tech", "Finance"],
        "net_worth": [1000, 2000, 1500, 1800, 1700],
    }
    dtm.data = _normalize_data(data)
    sorted_data = dtm.sort_values(by="net_worth", descending=False).data

    with pytest.raises(KeyError):
        _res = dtm.sort_values(by="missing_column", descending=True).data

    expected_data = {
        "company": [
            "Company A",
            "Company C",
            "Company E",
            "Company D",
            "Company B",
        ],
        "type": ["Tech", "Health", "Finance", "Tech", "Finance"],
        "net_worth": [1000, 1500, 1700, 1800, 2000],
    }
    assert sorted_data == _normalize_data(expected_data)


def test_sort_dict_of_tuples(dtm: DefaultTableManager) -> None:
    data = {
        "key1": (42, 17, 23),
        "key2": (99, 8, 4),
        "key3": (34, 65, 12),
        "key4": (1, 2, 3),
        "key5": (7, 9, 11),
    }
    dtm.data = _normalize_data(data)
    sorted_data = dtm.sort_values(by="key1", descending=True).data

    with pytest.raises(KeyError):
        _res = dtm.sort_values(by="missing_column", descending=True).data

    expected_data = [
        {"key1": 42, "key2": 99, "key3": 34, "key4": 1, "key5": 7},
        {"key1": 23, "key2": 4, "key3": 12, "key4": 3, "key5": 11},
        {"key1": 17, "key2": 8, "key3": 65, "key4": 2, "key5": 9},
    ]
    assert sorted_data == _normalize_data(expected_data)


def test_value() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data)
    assert list(table.value) == []


def test_value_with_selection() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data)
    assert list(table._convert_value(["0", "2"])) == ["banana", "cherry"]


def test_value_with_initial_selection() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data, initial_selection=[0, 2])
    assert table.value == ["banana", "cherry"]


def test_invalid_initial_selection() -> None:
    data = ["banana", "apple"]
    with pytest.raises(IndexError):
        ui.table(data, initial_selection=[2])

    with pytest.raises(TypeError):
        ui.table(data, initial_selection=["apple"])

    # multiple rows cannot be selected for single selection mode
    with pytest.raises(ValueError):
        ui.table(data, selection="single", initial_selection=[0, 1])


def test_value_with_sorting_then_selection() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data)

    table._search(
        SearchTableArgs(
            sort=SortArgs("value", descending=True),
            page_size=10,
            page_number=0,
        )
    )
    assert list(table._convert_value(["0"])) == [
        {"value": "elderberry"},
    ]

    table._search(
        SearchTableArgs(
            sort=SortArgs(
                "value",
                descending=False,
            ),
            page_size=10,
            page_number=0,
        )
    )
    assert list(table._convert_value(["0"])) == [
        {"value": "apple"},
    ]


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"a": ["x", "z", "y"]}, exclude=["ibis", "duckdb", "pyarrow"]
    ),
)
def test_value_with_sorting_then_selection_dfs(df: Any) -> None:
    import narwhals as nw

    table = ui.table(df)
    table._search(
        SearchTableArgs(
            sort=SortArgs("a", descending=True),
            page_size=10,
            page_number=0,
        )
    )
    value = table._convert_value(["0"])
    assert not isinstance(value, nw.DataFrame)
    assert nw.from_native(value)["a"][0] == "x"

    table._search(
        SearchTableArgs(
            sort=SortArgs("a", descending=False),
            page_size=10,
            page_number=0,
        )
    )
    value = table._convert_value(["0"])
    assert not isinstance(value, nw.DataFrame)
    assert nw.from_native(value)["a"][0] == "x"


def test_value_with_search_then_selection() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data)

    table._search(
        SearchTableArgs(
            query="apple",
            page_size=10,
            page_number=0,
        )
    )
    assert list(table._convert_value(["0"])) == [
        {"value": "apple"},
    ]

    table._search(
        SearchTableArgs(
            query="banana",
            page_size=10,
            page_number=0,
        )
    )
    assert list(table._convert_value(["0"])) == [
        {"value": "banana"},
    ]

    # Rows not in the search are not selected
    with pytest.raises(IndexError):
        table._convert_value(["2"])

    # empty search
    table._search(
        SearchTableArgs(
            page_size=10,
            page_number=0,
        )
    )
    assert list(table._convert_value(["2"])) == ["cherry"]


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"a": ["foo", "bar", "baz"]}, exclude=["ibis", "duckdb", "pyarrow"]
    ),
)
def test_value_with_search_then_selection_dfs(df: Any) -> None:
    import narwhals as nw

    table = ui.table(df)
    table._search(
        SearchTableArgs(
            query="bar",
            page_size=10,
            page_number=0,
        )
    )
    value = table._convert_value(["1"])
    assert not isinstance(value, nw.DataFrame)
    assert nw.from_native(value)["a"][0] == "bar"

    table._search(
        SearchTableArgs(
            query="foo",
            page_size=10,
            page_number=0,
        )
    )
    # Can still select rows not in the search
    value = table._convert_value(["0", "1"])
    assert not isinstance(value, nw.DataFrame)
    assert nw.from_native(value)["a"][0] == "foo"
    assert nw.from_native(value)["a"][1] == "bar"
    # empty search
    table._search(
        SearchTableArgs(
            page_size=10,
            page_number=0,
        )
    )
    value = table._convert_value(["2"])
    assert not isinstance(value, nw.DataFrame)
    assert nw.from_native(value)["a"][0] == "baz"


def test_value_with_selection_then_sorting_dict_of_lists() -> None:
    data = {
        "company": [
            "Company A",
            "Company B",
            "Company C",
            "Company D",
            "Company E",
        ],
        "type": ["Tech", "Finance", "Health", "Tech", "Finance"],
        "net_worth": [1000, 2000, 1500, 1800, 1700],
    }
    table = ui.table(data)

    table._search(
        SearchTableArgs(
            page_size=10,
            page_number=0,
        )
    )
    assert table._convert_value(["0", "2"])["company"] == [
        "Company A",
        "Company C",
    ]

    table._search(
        SearchTableArgs(
            sort=SortArgs("net_worth", descending=True),
            page_size=10,
            page_number=0,
        )
    )
    assert table._convert_value(["0", "2"])["company"] == [
        "Company B",
        "Company E",
    ]


def test_search_sort_nonexistent_columns() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data)

    # no error raised
    table._search(
        SearchTableArgs(
            sort=SortArgs("missing_column", descending=False),
            page_size=10,
            page_number=0,
        )
    )

    assert table._convert_value(["0"]) == ["banana"]


def test_table_with_too_many_columns_passes() -> None:
    data = {str(i): [1] for i in range(101)}
    assert ui.table(data) is not None


def test_table_with_too_many_rows_gets_clamped() -> None:
    data = {"a": list(range(20_002))}
    table = ui.table(data)
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 10
    assert table._component_args["total-rows"] == 20_002
    assert len(table._component_args["data"]) == 10


def test_table_too_large_pagesize_throws_error() -> None:
    data = {"a": list(range(20_002))}
    with pytest.raises(ValueError) as e:
        _ = ui.table(data, page_size=201)
    assert "limited to 200 rows" in str(e.value)


def test_can_get_second_page() -> None:
    data = {"a": list(range(40))}
    table = ui.table(data)
    result = table._search(
        SearchTableArgs(
            page_size=10,
            page_number=1,
        )
    )
    assert len(result.data) == 10
    assert result.data[0]["a"] == 10
    assert result.data[-1]["a"] == 19


def test_can_get_second_page_with_search() -> None:
    data = {"a": list(range(40))}
    table = ui.table(data)
    result = table._search(
        SearchTableArgs(
            query="2",
            page_size=5,
            page_number=1,
        )
    )
    assert len(result.data) == 5
    assert result.data[0]["a"] == 23
    assert result.data[-1]["a"] == 27


@pytest.mark.parametrize(
    "df",
    create_dataframes({"a": list(range(40))}, ["ibis"]),
)
def test_can_get_second_page_with_search_df(df: Any) -> None:
    import polars as pl

    table = ui.table(df)
    result = table._search(
        SearchTableArgs(
            query="2",
            page_size=5,
            page_number=1,
        )
    )
    mime_type, data = from_data_uri(result.data)
    assert mime_type == "text/csv"
    data = pl.read_csv(data)
    assert len(data) == 5
    assert int(data["a"][0]) == 23
    assert int(data["a"][-1]) == 27


def test_with_no_pagination() -> None:
    data = {"a": list(range(20))}
    table = ui.table(data, pagination=False)
    assert table._component_args["pagination"] is False
    assert table._component_args["page-size"] == 20
    assert table._component_args["total-rows"] == 20
    assert len(table._component_args["data"]) == 20


def test_table_with_too_many_rows_and_custom_total() -> None:
    data = {"a": list(range(40))}
    table = ui.table(
        data, _internal_column_charts_row_limit=30, _internal_total_rows=300
    )
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 10
    assert table._component_args["total-rows"] == 300
    assert len(table._component_args["data"]) == 10


def test_table_with_too_many_rows_unknown_total() -> None:
    data = {"a": list(range(40))}
    table = ui.table(
        data,
        _internal_column_charts_row_limit=30,
        _internal_total_rows="too_many",
    )
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 10
    assert table._component_args["total-rows"] == "too_many"
    assert len(table._component_args["data"]) == 10


def test_empty_table() -> None:
    table = ui.table([])
    assert table._component_args["total-rows"] == 0


def test_table_with_too_many_rows_column_summaries_disabled() -> None:
    data = {"a": list(range(20))}
    table = ui.table(data, _internal_summary_row_limit=10)

    summaries_disabled = table._get_column_summaries(EmptyArgs())
    assert summaries_disabled.is_disabled is True

    # search results are 2 and 12
    table._search(
        SearchTableArgs(
            query="2",
            page_size=10,
            page_number=0,
        )
    )
    summaries_enabled = table._get_column_summaries(EmptyArgs())
    assert summaries_enabled.is_disabled is False


def test_with_too_many_rows_column_charts_disabled() -> None:
    data = {"a": list(range(20))}
    table = ui.table(data, _internal_column_charts_row_limit=10)

    charts_disabled = table._get_column_summaries(EmptyArgs())
    assert charts_disabled.is_disabled is False
    assert charts_disabled.data is None

    # search results are 2 and 12
    table._search(
        SearchTableArgs(
            query="2",
            page_size=10,
            page_number=0,
        )
    )
    charts_enabled = table._get_column_summaries(EmptyArgs())
    assert charts_enabled.is_disabled is False


def test__get_column_summaries_after_search() -> None:
    data = {"a": list(range(20))}
    table = ui.table(data)

    # search results are 2 and 12
    table._search(
        SearchTableArgs(
            query="2",
            page_size=10,
            page_number=0,
        )
    )
    summaries = table._get_column_summaries(EmptyArgs())
    assert summaries.is_disabled is False
    assert summaries.data == [{"a": 2}, {"a": 12}]
    # We don't have column summaries for non-dataframe data
    assert summaries.summaries[0].min is None
    assert summaries.summaries[0].max is None


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test__get_column_summaries_after_search_df() -> None:
    import pandas as pd

    table = ui.table(pd.DataFrame({"a": list(range(20))}))
    summaries = table._get_column_summaries(EmptyArgs())
    assert summaries.is_disabled is False
    assert isinstance(summaries.data, str)
    assert summaries.data.startswith("data:text/csv;base64,")
    assert summaries.summaries[0].min == 0
    assert summaries.summaries[0].max == 19

    # search results are 2 and 12
    table._search(
        SearchTableArgs(
            query="2",
            page_size=10,
            page_number=0,
        )
    )
    summaries = table._get_column_summaries(EmptyArgs())
    assert summaries.is_disabled is False
    assert isinstance(summaries.data, str)
    assert summaries.data.startswith("data:text/csv;base64,")
    # We don't have column summaries for non-dataframe data
    assert summaries.summaries[0].min == 2
    assert summaries.summaries[0].max == 12
    assert summaries.summaries[0].nulls == 0


def test_show_column_summaries_modes():
    data = {"a": list(range(20))}

    # Test stats-only mode
    table_stats = ui.table(data, show_column_summaries="stats")
    summaries_stats = table_stats._get_column_summaries(EmptyArgs())
    assert summaries_stats.is_disabled is False
    assert summaries_stats.data is None
    assert len(summaries_stats.summaries) > 0

    # Test chart-only mode
    table_chart = ui.table(data, show_column_summaries="chart")
    summaries_chart = table_chart._get_column_summaries(EmptyArgs())
    assert summaries_chart.is_disabled is False
    assert summaries_chart.data is not None
    assert len(summaries_chart.summaries) == 0

    # Test default mode (both stats and chart)
    table_both = ui.table(data, show_column_summaries=True)
    summaries_both = table_both._get_column_summaries(EmptyArgs())
    assert summaries_both.is_disabled is False
    assert summaries_both.data is not None
    assert len(summaries_both.summaries) > 0

    # Test disabled mode
    table_disabled = ui.table(data, show_column_summaries=False)
    summaries_disabled = table_disabled._get_column_summaries(EmptyArgs())
    assert summaries_disabled.is_disabled is False
    assert summaries_disabled.data is None
    assert len(summaries_disabled.summaries) == 0

    # Test Default behavior
    table_default = ui.table(data)
    summaries_default = table_default._get_column_summaries(EmptyArgs())
    assert summaries_default.is_disabled is False
    assert summaries_default.data is not None
    assert len(summaries_default.summaries) > 0


def test_table_with_frozen_columns() -> None:
    data = {
        "a": list(range(20)),
        "b": list(range(20)),
        "c": list(range(20)),
        "d": list(range(20)),
        "e": list(range(20)),
    }
    table = ui.table(
        data, freeze_columns_left=["a", "b"], freeze_columns_right=["d", "e"]
    )
    assert table._component_args["freeze-columns-left"] == ["a", "b"]
    assert table._component_args["freeze-columns-right"] == ["d", "e"]


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_table_with_filtered_columns_pandas() -> None:
    import pandas as pd

    table = ui.table(pd.DataFrame({"a": [1, 2, 3], "b": ["abc", "def", None]}))
    result = table._search(
        SearchTableArgs(
            filters=[Condition(column_id="b", operator="contains", value="f")],
            page_size=10,
            page_number=0,
        )
    )
    assert result.total_rows == 1


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_table_with_filtered_columns_polars() -> None:
    import polars as pl

    table = ui.table(pl.DataFrame({"a": [1, 2, 3], "b": ["abc", "def", None]}))
    result = table._search(
        SearchTableArgs(
            filters=[Condition(column_id="b", operator="contains", value="a")],
            page_size=10,
            page_number=0,
        )
    )

    assert result.total_rows == 1


def test_show_column_summaries_default():
    # Test default behavior (True for < 40 columns, False otherwise)
    small_data = {"col" + str(i): range(5) for i in range(39)}
    table_small = ui.table(small_data)
    assert table_small._show_column_summaries is True
    assert table_small._component_args["show-column-summaries"] is True

    large_data = {"col" + str(i): range(5) for i in range(41)}
    table_large = ui.table(large_data)
    assert table_large._show_column_summaries is False
    assert table_large._component_args["show-column-summaries"] is False

    # explicitly set to True
    table_true = ui.table(large_data, show_column_summaries=True)
    assert table_true._show_column_summaries is True
    assert table_true._component_args["show-column-summaries"] is True


def test_show_column_summaries_explicit():
    # Test explicit setting of show_column_summaries
    data = {"a": [1, 2, 3], "b": [4, 5, 6]}
    table_true = ui.table(data, show_column_summaries=True)
    assert table_true._show_column_summaries is True
    assert table_true._component_args["show-column-summaries"] is True

    table_false = ui.table(data, show_column_summaries=False)
    assert table_false._show_column_summaries is False
    assert table_false._component_args["show-column-summaries"] is False


def test_show_column_summaries_disabled():
    # Test when show_column_summaries is explicitly set to False
    table = ui.table(
        {"a": [1, 2, 3], "b": [4, 5, 6]}, show_column_summaries=False
    )

    summaries = table._get_column_summaries(EmptyArgs())
    assert summaries.is_disabled is False
    assert summaries.data is None
    assert len(summaries.summaries) == 0


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_show_download():
    import pandas as pd

    data = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    table_default = ui.table(data)
    assert table_default._component_args["show-download"] is True

    table_true = ui.table(data, show_download=True)
    assert table_true._component_args["show-download"] is True

    table_false = ui.table(data, show_download=False)
    assert table_false._component_args["show-download"] is False


def test_pagination_behavior() -> None:
    # Test with default page_size=10
    data = {"a": list(range(8))}
    table = ui.table(data)
    assert table._component_args["pagination"] is False
    assert table._component_args["page-size"] == 10
    assert len(table._component_args["data"]) == 8

    # Test with custom page_size=5 and data <= page_size
    data = {"a": list(range(5))}
    table = ui.table(data, page_size=5)
    assert table._component_args["pagination"] is False
    assert table._component_args["page-size"] == 5
    assert len(table._component_args["data"]) == 5

    # Test with custom page_size=5 and data > page_size
    data = {"a": list(range(8))}
    table = ui.table(data, page_size=5)
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 5
    assert len(table._component_args["data"]) == 5

    # Test with explicit pagination=True
    data = {"a": list(range(5))}
    table = ui.table(data, pagination=True, page_size=5)
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 5
    assert len(table._component_args["data"]) == 5


def test_column_clamping():
    # Create data with many columns
    data = {f"col{i}": [1, 2, 3] for i in range(100)}

    # Test default max_columns
    table = ui.table(data)
    assert len(table._manager.get_column_names()) == 100
    assert table._component_args["total-columns"] == 100
    assert len(table._component_args["data"][0].keys()) == 50
    assert table._component_args["field-types"] is None

    # Test custom max_columns
    table = ui.table(data, max_columns=20)
    assert len(table._manager.get_column_names()) == 100
    assert table._component_args["total-columns"] == 100
    assert len(table._component_args["data"][0].keys()) == 20
    assert table._component_args["field-types"] is None

    # Test no clamping
    table = ui.table(data, max_columns=None)
    assert len(table._manager.get_column_names()) == 100
    assert table._component_args["total-columns"] == 100
    assert len(table._component_args["data"][0].keys()) == 100
    assert table._component_args["field-types"] is None


def test_column_clamping_with_small_data():
    data = {f"col{i}": [1, 2, 3] for i in range(10)}

    # Should not clamp when under max_columns
    table = ui.table(data)
    assert len(table._manager.get_column_names()) == 10
    assert table._component_args["total-columns"] == 10
    assert len(table._component_args["data"][0].keys()) == 10
    assert table._component_args["field-types"] is None


def test_search_clamping_columns():
    data = {f"col{i}": [1, 2, 3] for i in range(100)}
    table = ui.table(data, max_columns=20)

    # Perform a search
    search_args = SearchTableArgs(page_size=10, page_number=0, query="1")
    response = table._search(search_args)

    # Check that the search result is clamped
    assert len(response.data[0].keys()) == 20

    # Check that selection is not clamped
    table._selected_manager = table._searched_manager.select_rows([0])
    selected_data = table._selected_manager.data
    assert len(selected_data) == 100


def test_search_no_clamping_columns():
    data = {f"col{i}": [1, 2, 3] for i in range(100)}
    table = ui.table(data, max_columns=None)

    # Perform a search
    search_args = SearchTableArgs(page_size=10, page_number=0, query="1")
    response = table._search(search_args)

    # Check that the search result is not clamped
    assert len(response.data[0].keys()) == 100

    # Check that selection is not clamped
    table._selected_manager = table._searched_manager.select_rows([0])
    selected_data = table._selected_manager.data
    assert len(selected_data) == 100


def test_column_clamping_with_exact_max_columns():
    data = {f"col{i}": [1, 2, 3] for i in range(50)}
    table = ui.table(data, max_columns=50)

    # Check that the table is not clamped
    assert len(table._manager.get_column_names()) == 50
    assert table._component_args["total-columns"] == 50
    assert len(table._component_args["data"][0].keys()) == 50
    assert table._component_args["field-types"] is None


def test_column_clamping_with_more_than_max_columns():
    data = {f"col{i}": [1, 2, 3] for i in range(60)}
    table = ui.table(data, max_columns=50)

    # Check that the table is clamped
    assert len(table._manager.get_column_names()) == 60
    assert table._component_args["total-columns"] == 60
    assert len(table._component_args["data"][0].keys()) == 50
    assert table._component_args["field-types"] is None


def test_column_clamping_with_no_columns():
    table = ui.table([], max_columns=50)

    # Check that the table handles no columns gracefully
    assert len(table._manager.get_column_names()) == 1
    assert table._component_args["total-columns"] == 1
    assert len(table._component_args["data"]) == 0
    assert table._component_args["field-types"] is None


def test_column_clamping_with_single_column():
    data = {"col1": [1, 2, 3]}
    table = ui.table(data, max_columns=50)

    # Check that the table handles a single column gracefully
    assert len(table._manager.get_column_names()) == 1
    assert table._component_args["total-columns"] == 1
    assert len(table._component_args["data"][0].keys()) == 1
    assert table._component_args["field-types"] is None


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_column_clamping_with_polars():
    import polars as pl

    data = pl.DataFrame({f"col{i}": [1, 2, 3] for i in range(60)})
    table = ui.table(data)

    # Check that the table is clamped
    assert len(table._manager.get_column_names()) == 60
    assert table._component_args["total-columns"] == 60
    csv = from_data_uri(table._component_args["data"])[1].decode("utf-8")
    headers = csv.split("\n")[0].split(",")
    assert len(headers) == 50  # 50 columns
    assert len(table._component_args["field-types"]) == 50

    table = ui.table(data, max_columns=40)

    # Check that the table is clamped
    assert len(table._manager.get_column_names()) == 60
    assert table._component_args["total-columns"] == 60
    csv = from_data_uri(table._component_args["data"])[1].decode("utf-8")
    headers = csv.split("\n")[0].split(",")
    assert len(headers) == 40  # 40 columns
    assert len(table._component_args["field-types"]) == 40

    table = ui.table(data, max_columns=None)

    # Check that the table is not clamped
    assert len(table._manager.get_column_names()) == 60
    assert table._component_args["total-columns"] == 60
    csv = from_data_uri(table._component_args["data"])[1].decode("utf-8")
    headers = csv.split("\n")[0].split(",")

    assert len(headers) == 61  # 60 columns + 1 selection column
    assert len(table._component_args["field-types"]) == 60


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_dataframe_with_int_column_names():
    import warnings

    import pandas as pd

    data = pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=[0, 1, 2])
    with warnings.catch_warnings(record=True) as w:
        table = ui.table(data)
        # Check that warnings were made
        assert len(w) > 0
        assert "DataFrame has integer column names" in str(w[0].message)

    # Check that the table handles integer column names correctly
    assert table._manager.get_column_names() == [0, 1, 2]
    assert table._component_args["total-columns"] == 3
