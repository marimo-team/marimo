# Copyright 2026 Marimo. All rights reserved.
"""Shared fixtures and notebook fixtures for the benchmark suite.

The notebooks used by the benchmarks are generated deterministically so that
the measured workloads stay stable across commits: a benchmark should only
move when marimo's code changes, not when a tutorial gets a new paragraph.
"""

from __future__ import annotations

import pytest

from benchmarks.notebooks import (
    generate_markdown_notebook,
    generate_notebook_source,
)


@pytest.fixture(scope="session")
def small_notebook() -> str:
    """A notebook with a handful of cells."""
    return generate_notebook_source(n_cells=5)


@pytest.fixture(scope="session")
def notebook() -> str:
    """A notebook of a size representative of a real-world notebook."""
    return generate_notebook_source(n_cells=50)


@pytest.fixture(scope="session")
def large_notebook() -> str:
    """A large notebook, to exercise super-linear behavior."""
    return generate_notebook_source(n_cells=200)


@pytest.fixture(scope="session")
def markdown_notebook() -> str:
    """A markdown-flavored marimo notebook."""
    return generate_markdown_notebook(n_cells=50)
