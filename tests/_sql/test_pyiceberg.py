# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from marimo._data.models import DataTable, DataTableColumn, Namespace, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.pyiceberg import PyIcebergEngine
from marimo._sql.engines.types import EngineCatalog, QueryEngine
from marimo._types.ids import VariableName

HAS_PYICEBERG = DependencyManager.pyiceberg.has()


def _table_nodes_at_root(children: list | None) -> list[DataTable]:
    return [node for node in (children or []) if isinstance(node, DataTable)]


def _schema_nodes(children: list | None) -> list[Schema]:
    return [node for node in (children or []) if isinstance(node, Schema)]


def _namespace_nodes(children: list | None) -> list[Namespace]:
    return [node for node in (children or []) if isinstance(node, Namespace)]


def _table_nodes(node: Schema | Namespace) -> list[DataTable]:
    if isinstance(node, Schema):
        return node.tables or []
    return [
        child
        for child in (node.children or [])
        if isinstance(child, DataTable)
    ]


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

    # Create namespaces, including nested ones
    catalog.create_namespace("default")
    catalog.create_namespace("test_namespace")
    catalog.create_namespace(("top", "nested"))
    catalog.create_namespace(("top", "nested", "deep"))

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
    catalog.create_table(("top", "nested", "table4"), schema)
    catalog.create_table(("top", "nested", "deep", "table5"), schema)

    assert len(catalog.list_tables("default")) == 2
    assert len(catalog.list_tables("test_namespace")) == 1
    assert len(catalog.list_tables(("top", "nested"))) == 1
    assert len(catalog.list_tables(("top", "nested", "deep"))) == 1

    yield catalog

    catalog.drop_table(("default", "table1"))
    catalog.drop_table(("default", "table2"))
    catalog.drop_table(("test_namespace", "table3"))
    catalog.drop_table(("top", "nested", "table4"))
    catalog.drop_table(("top", "nested", "deep", "table5"))


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
        schema_name="",
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
    """Each top-level namespace is a Database; sub-namespaces are recursive
    child Schemas."""
    engine_name = VariableName("my_iceberg")
    engine = PyIcebergEngine(memory_catalog, engine_name=engine_name)

    # Test with all parameters True (eager)
    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )

    assert isinstance(databases, list)
    # Only top-level namespaces become Databases.
    by_name = {db.name: db for db in databases}
    assert set(by_name) == {"default", "test_namespace", "top"}

    # "default" has its own tables as direct children, no sub-namespaces.
    default_tables = _table_nodes_at_root(by_name["default"].children)
    assert by_name["default"].dialect == "iceberg"
    assert len(default_tables) == 2

    assert len(_table_nodes_at_root(by_name["test_namespace"].children)) == 1

    # "top" has no tables of its own but contains the "nested" sub-namespace.
    top_tables = _table_nodes_at_root(by_name["top"].children)
    top_namespaces = {
        n.name: n for n in _namespace_nodes(by_name["top"].children)
    }
    assert set(top_namespaces) == {"nested"}
    assert top_tables == []

    nested = top_namespaces["nested"]
    assert [t.name for t in _table_nodes(nested)] == ["table4"]
    # "nested" recursively contains "deep", which holds "table5".
    deep_by_name = {n.name: n for n in _namespace_nodes(nested.children)}
    assert set(deep_by_name) == {"deep"}
    assert [t.name for t in _table_nodes(deep_by_name["deep"])] == ["table5"]

    # Test with include_tables=False (schemas listed, tables deferred)
    databases = engine.get_databases(
        include_schemas=True, include_tables=False, include_table_details=True
    )
    by_name = {db.name: db for db in databases}
    assert set(by_name) == {"default", "test_namespace", "top"}
    top_namespaces = {
        n.name: n for n in _namespace_nodes(by_name["top"].children)
    }
    # Sub-namespace is present but its tables/children are deferred.
    assert set(top_namespaces) == {"nested"}
    nested = top_namespaces["nested"]
    assert nested.children is None


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_get_databases_lazy_schemas(memory_catalog: Catalog) -> None:
    """With include_schemas=False, databases defer schema discovery."""
    engine = PyIcebergEngine(
        memory_catalog, engine_name=VariableName("my_iceberg")
    )

    databases = engine.get_databases(
        include_schemas=False,
        include_tables=False,
        include_table_details=False,
    )
    assert {db.name for db in databases} == {
        "default",
        "test_namespace",
        "top",
    }
    for db in databases:
        assert db.children is None


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_connection_is_lazy(memory_catalog: Catalog) -> None:
    """The initial connection lists top-level namespaces and the first level of
    sub-namespaces, but defers their tables and deeper namespaces until expand."""
    from marimo._sql.get_engines import engine_to_data_source_connection

    engine = PyIcebergEngine(
        memory_catalog, engine_name=VariableName("my_iceberg")
    )
    # The first level of schemas is eager; tables/columns are deferred.
    assert engine.inference_config.auto_discover_schemas is True
    assert engine.inference_config.auto_discover_tables is False
    assert engine.inference_config.auto_discover_columns is False

    connection = engine_to_data_source_connection(
        VariableName("my_iceberg"), engine
    )
    by_name = {db.name: db for db in connection.databases}
    assert set(by_name) == {"default", "test_namespace", "top"}

    # First-level children are present...
    top = by_name["top"]
    top_namespaces = {n.name: n for n in _namespace_nodes(top.children)}
    assert set(top_namespaces) == {"nested"}

    # ...but their tables and deeper sub-namespaces are deferred.
    assert _table_nodes_at_root(top.children) == []
    nested = top_namespaces["nested"]
    assert nested.children is None


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_get_schemas_by_path(memory_catalog: Catalog) -> None:
    """get_schemas lists one level at a time, selected by catalog_path."""
    engine = PyIcebergEngine(
        memory_catalog, engine_name=VariableName("my_iceberg")
    )

    # Top level: immediate child "nested" (deferred, not recursed).
    nodes = engine.get_schemas(
        database="top",
        include_tables=False,
        include_table_details=False,
        catalog_path=[],
    )
    assert [n.name for n in nodes] == ["nested"]
    nested = nodes[0]
    assert isinstance(nested, Namespace)
    assert nested.children is None

    # Immediate child of "top.nested" is "deep".
    nodes = engine.get_schemas(
        database="top",
        include_tables=False,
        include_table_details=False,
        catalog_path=["nested"],
    )
    assert [n.name for n in nodes] == ["deep"]
    assert isinstance(nodes[0], Namespace)

    # "top.nested.deep" is a leaf.
    assert (
        engine.get_schemas(
            database="top",
            include_tables=False,
            include_table_details=False,
            catalog_path=["nested", "deep"],
        )
        == []
    )


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_nested_namespace_tables(memory_catalog: Catalog) -> None:
    """Tables of a nested namespace are reachable via its dotted name."""
    engine = PyIcebergEngine(
        memory_catalog, engine_name=VariableName("my_iceberg")
    )

    tables = engine.get_tables_in_schema(
        schema="",
        database="top.nested",
        include_table_details=True,
    )
    assert [t.name for t in tables] == ["table4"]
    assert tables[0].num_columns == 3

    table = engine.get_table_details(
        table_name="table5",
        schema_name="",
        database_name="top.nested.deep",
    )
    assert table is not None
    assert table.name == "table5"
    assert len(table.columns) == 3


@pytest.mark.skipif(not HAS_PYICEBERG, reason="PyIceberg not installed")
def test_pyiceberg_table_calls_fold_catalog_path(
    memory_catalog: Catalog,
) -> None:
    """The handler passes the top-level `database` plus a `catalog_path`; the
    engine folds them into a dotted namespace internally (this replaced the
    handler-side `_table_database` helper)."""
    engine = PyIcebergEngine(
        memory_catalog, engine_name=VariableName("my_iceberg")
    )

    # database + catalog_path is equivalent to the pre-folded dotted database.
    tables = engine.get_tables_in_schema(
        schema="",
        database="top",
        catalog_path=["nested"],
        include_table_details=True,
    )
    assert [t.name for t in tables] == ["table4"]

    table = engine.get_table_details(
        table_name="table5",
        schema_name="",
        database_name="top",
        catalog_path=["nested", "deep"],
    )
    assert table is not None
    assert table.name == "table5"

    # Empty / missing catalog_path leaves the database untouched.
    assert PyIcebergEngine._qualified_namespace("top", []) == "top"
    assert PyIcebergEngine._qualified_namespace("top", None) == "top"
    assert (
        PyIcebergEngine._qualified_namespace("top", ["nested", "deep"])
        == "top.nested.deep"
    )


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
    assert len(databases) == 3
    by_name = {db.name: db for db in databases}
    assert len(_table_nodes_at_root(by_name["default"].children)) == 2

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
        assert len(databases) == 3
        for db in databases:
            assert db.children is None
