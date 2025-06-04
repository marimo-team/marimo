# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.redshift import RedshiftEngine
from marimo._sql.engines.types import EngineCatalog, QueryEngine
from marimo._types.ids import VariableName

HAS_REDSHIFT = DependencyManager.redshift_connector.has()

if TYPE_CHECKING:
    from collections.abc import Generator

    from redshift_connector import Connection


@pytest.fixture
def mock_connection() -> Generator[Connection, None, None]:
    """Create a mock Redshift connection for testing."""
    if not HAS_REDSHIFT:
        yield mock.MagicMock()
        return

    from redshift_connector import Connection

    # Create mock connection
    connection = mock.MagicMock(spec=Connection)

    # Mock cursor methods
    cursor = mock.MagicMock()
    connection.cursor.return_value = cursor

    yield connection


@pytest.mark.skipif(
    not HAS_REDSHIFT, reason="Redshift connector not installed"
)
def test_engine_compatibility(mock_connection: Connection) -> None:
    """Test engine compatibility checks."""
    assert RedshiftEngine.is_compatible(mock_connection)
    assert not RedshiftEngine.is_compatible(object())

    engine = RedshiftEngine(
        mock_connection, engine_name=VariableName("my_redshift")
    )
    assert isinstance(engine, RedshiftEngine)
    assert isinstance(engine, EngineCatalog)
    assert isinstance(engine, QueryEngine)


@pytest.mark.skipif(
    not HAS_REDSHIFT, reason="Redshift connector not installed"
)
def test_engine_name_initialization(mock_connection: Connection) -> None:
    """Test engine name initialization."""
    engine = RedshiftEngine(
        mock_connection, engine_name=VariableName("my_redshift")
    )
    assert engine._engine_name == VariableName("my_redshift")

    # Test default name
    engine = RedshiftEngine(mock_connection)
    assert engine._engine_name is None


@pytest.mark.skipif(
    not HAS_REDSHIFT, reason="Redshift connector not installed"
)
def test_redshift_engine_source_and_dialect(
    mock_connection: Connection,
) -> None:
    """Test RedshiftEngine source and dialect properties."""
    engine = RedshiftEngine(mock_connection)
    assert engine.source == "redshift"
    assert engine.dialect == "redshift"
