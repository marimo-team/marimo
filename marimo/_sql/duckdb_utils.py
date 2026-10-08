# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations


def is_duckdb_v2() -> bool:
    """Whether the installed DuckDB uses version 2 or later, including previews."""
    import duckdb
    from packaging.version import Version

    return Version(duckdb.__version__).major >= 2
