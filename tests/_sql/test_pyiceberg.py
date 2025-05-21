"""Tests for PyIceberg engine."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from marimo._data.models import DataTable, DataTableColumn
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.pyiceberg import PyIcebergEngine
from marimo._sql.engines.types import (
    NO_SCHEMA_NAME,
    EngineCatalog,
    QueryEngine,
)
from marimo._types.ids import VariableName

HAS_PYICEBERG = DependencyManager.pyiceberg.has()

if TYPE_CHECKING:
    from collections.abc import Generator

    from pyiceberg.catalog import Catalog


@pytest.fixture
def memory_catalog() -> Generator[Catalog, None, None]:
    """Create a mock PyIceberg catalog for testing."""
    if not HAS_PYICEBERG:
        yield mock.MagicMock()
        return

    from pyiceberg.catalog.memory import InMemoryCatalog
    from pyiceberg.schema import Schema as IcebergSchema
    from pyiceberg.types import (
        BooleanType,
        IntegerType,
        NestedField,
        StringType,
    )

    # Create mock catalog
    catalog = InMemoryCatalog("test_catalog")

    # Create namespaces
    catalog.create_namespace("default")
    catalog.create_namespace("test_namespace")

    # Create actual schema object with real fields
    schema = IcebergSchema(
        fields=[
            NestedField(
                field_id=1, name="id", field_type=IntegerType(), required=True
            ),
            NestedField(
                field_id=2, name="name", field_type=StringType(), required=True
            ),
            NestedField(
                field_id=3,
                name="active",
                field_type=BooleanType(),
                required=False,
            ),
        ]
    )

    catalog.create_table(("default", "table1"), schema)
    catalog.create_table(("default", "table2"), schema)
    catalog.create_table(("test_namespace", "table3"), schema)

    assert len(catalog.list_tables("default")) == 2
    assert len(catalog.list_tables("test_namespace")) == 1

    yield catalog

    catalog.drop_table(("default", "table1"))
    catalog.drop_table(("default", "table2"))
    catalog.drop_table(("test_namespace", "table3"))


def get_expected_table(
    table_name: str, include_table_details: bool = True
) -> DataTable:
    """Return expected table structure for tests."""
    return DataTable(
        source_type="catalog",
        source="iceberg",
        name=table_name,
        num_rows=None,
        num_columns=3 if include_table_details else None,
        variable_name=None,
        engine=VariableName("my_iceberg"),
        type="table",
        primary_keys=[] if not include_table_details else None,
        indexes=[] if not include_table_details else None,
        columns=[
            DataTableColumn(
                name="id",
                type="integer",
                external_type="int",
                sample_values=[],
            ),
            DataTableColumn(
                name="name",
                type="string",
                external_type="string",
                sample_values=[],
            ),
            DataTableColumn(
                name="active",
                type="boolean",
                external_type="boolean",
                sample_values=[],
            ),
        ]
        if include_table_details
        else [],
    )


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_engine_compatibility() -> None:
    """Test engine compatibility checks."""
    from pyiceberg.catalog.memory import InMemoryCatalog

    obj = object()
    mock_catalog = InMemoryCatalog("test_catalog")

    assert PyIcebergEngine.is_compatible(mock_catalog)
    assert not PyIcebergEngine.is_compatible(obj)

    engine = PyIcebergEngine(
        mock_catalog, engine_name=VariableName("my_iceberg")
    )
    assert isinstance(engine, PyIcebergEngine)
    assert isinstance(engine, EngineCatalog)
    assert not isinstance(engine, QueryEngine)


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_engine_name_initialization(memory_catalog: Catalog) -> None:
    """Test engine name initialization."""
    engine = PyIcebergEngine(
        memory_catalog, engine_name=VariableName("my_iceberg")
    )
    assert engine._engine_name == VariableName("my_iceberg")

    # Test default name
    engine = PyIcebergEngine(memory_catalog)
    assert engine._engine_name is None


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_engine_source_and_dialect(memory_catalog: Catalog) -> None:
    """Test PyIcebergEngine source and dialect properties."""
    engine = PyIcebergEngine(memory_catalog)
    assert engine.source == "iceberg"
    assert engine.dialect == "iceberg"


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_engine_get_database_name(memory_catalog: Catalog) -> None:
    """Test PyIcebergEngine get_database_name."""
    engine = PyIcebergEngine(
        memory_catalog, engine_name=VariableName("my_iceberg")
    )
    assert engine.get_default_database() is None
    assert engine.get_default_schema() is None


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_execute(memory_catalog: Catalog) -> None:
    """Test PyIceberg execute raises NotImplementedError."""
    engine = PyIcebergEngine(
        memory_catalog, engine_name=VariableName("my_iceberg")
    )
    assert isinstance(engine, EngineCatalog)
    assert not isinstance(engine, QueryEngine)
    with pytest.raises(AttributeError):
        engine.execute("SELECT * FROM table")


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_get_table_details(memory_catalog: Catalog) -> None:
    """Test PyIcebergEngine get_table_details method."""
    engine = PyIcebergEngine(
        memory_catalog, engine_name=VariableName("my_iceberg")
    )
    table = engine.get_table_details(
        table_name="table1",
        schema_name=NO_SCHEMA_NAME,
        database_name="default",
    )

    assert table is not None
    assert table.source == "iceberg"
    assert table.name == "table1"
    assert table.num_columns == 3
    assert len(table.columns) == 3
    assert table.columns[0].name == "id"
    assert table.columns[0].type == "integer"
    assert table.columns[1].name == "name"
    assert table.columns[1].type == "string"
    assert table.columns[2].name == "active"
    assert table.columns[2].type == "boolean"


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_get_tables_in_schema(memory_catalog: Catalog) -> None:
    """Test PyIcebergEngine get_tables_in_schema method."""
    engine = PyIcebergEngine(
        memory_catalog, engine_name=VariableName("my_iceberg")
    )

    # Test with include_table_details=True
    tables = engine.get_tables_in_schema(
        schema="unused", database="default", include_table_details=True
    )

    assert isinstance(tables, list)
    assert len(tables) == 2
    assert tables[0].name == "table1"
    assert tables[1].name == "table2"
    assert tables[0].num_columns == 3
    assert tables[1].num_columns == 3

    # Test with include_table_details=False
    tables = engine.get_tables_in_schema(
        schema="unused", database="default", include_table_details=False
    )

    assert isinstance(tables, list)
    assert len(tables) == 2
    assert tables[0].name == "table1"
    assert tables[1].name == "table2"
    assert tables[0].num_columns is None
    assert tables[1].num_columns is None
    assert tables[0].columns == []
    assert tables[1].columns == []


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_get_databases(memory_catalog: Catalog) -> None:
    """Test PyIcebergEngine get_databases method."""
    engine_name = VariableName("my_iceberg")
    engine = PyIcebergEngine(memory_catalog, engine_name=engine_name)

    # Test with all parameters True
    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )

    assert isinstance(databases, list)
    assert len(databases) == 2
    assert databases[0].name == "default"
    assert databases[0].dialect == "iceberg"
    assert len(databases[0].schemas) == 1
    assert databases[0].schemas[0].name == NO_SCHEMA_NAME
    assert len(databases[0].schemas[0].tables) == 2

    assert databases[1].name == "test_namespace"
    assert len(databases[1].schemas) == 1
    assert databases[1].schemas[0].name == NO_SCHEMA_NAME
    assert len(databases[1].schemas[0].tables) == 1

    # Test with include_tables=False
    databases = engine.get_databases(
        include_schemas=True, include_tables=False, include_table_details=True
    )

    assert isinstance(databases, list)
    assert len(databases) == 2
    assert databases[0].name == "default"
    assert len(databases[0].schemas) == 1
    assert databases[0].schemas[0].name == NO_SCHEMA_NAME
    assert len(databases[0].schemas[0].tables) == 0

    assert databases[1].name == "test_namespace"
    assert len(databases[1].schemas) == 1
    assert databases[1].schemas[0].name == NO_SCHEMA_NAME
    assert len(databases[1].schemas[0].tables) == 0


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_auto_discovery(memory_catalog: Catalog) -> None:
    """Test PyIcebergEngine auto discovery behavior."""
    engine_name = VariableName("my_iceberg")
    engine = PyIcebergEngine(memory_catalog, engine_name=engine_name)

    # Test with auto parameters (should behave like True for PyIceberg)
    databases = engine.get_databases(
        include_schemas="auto",
        include_tables="auto",
        include_table_details="auto",
    )

    assert isinstance(databases, list)
    assert len(databases) == 2
    assert databases[0].schemas[0].name == NO_SCHEMA_NAME
    assert len(databases[0].schemas[0].tables) == 2

    # Test with _is_cheap_discovery mocked to return False
    with mock.patch.object(
        PyIcebergEngine, "_is_cheap_discovery", return_value=False
    ):
        databases = engine.get_databases(
            include_schemas="auto",
            include_tables="auto",
            include_table_details="auto",
        )

        assert isinstance(databases, list)
        assert len(databases) == 2
        assert len(databases[0].schemas[0].tables) == 0
