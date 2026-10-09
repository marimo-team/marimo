# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests._plugins.ui._impl.tables import geometry_fixtures

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def duckdb_export_conn() -> Iterator[Any]:
    conn = geometry_fixtures.duckdb_export_connection()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def duckdb_crs_conn() -> Iterator[Any]:
    conn = geometry_fixtures.duckdb_crs_geometry_connection()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def duckdb_spatial_conn() -> Iterator[Any]:
    conn = geometry_fixtures.duckdb_spatial_connection()
    try:
        yield conn
    finally:
        conn.close()
