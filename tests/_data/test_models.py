from marimo._data.models import DataTableColumn


def test_data_table_column_post_init() -> None:
    column = DataTableColumn(
        name=123,
        type="string",
        external_type="string",
        sample_values=[],
    )
    assert column.name == "123"
