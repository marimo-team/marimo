from marimo._data.models import DataTableColumn
from tests.utils import assert_serialize_roundtrip


def test_data_table_column_post_init() -> None:
    column = DataTableColumn(
        name=123,
        type="string",
        external_type="string",
        sample_values=[],
    )
    assert column.name == "123"

    assert_serialize_roundtrip(column)
