# Copyright 2026 Marimo. All rights reserved.
"""Pre-execute the input-free portion of a notebook's DAG.

The :func:`build_notebook` entry point materializes the results of
input-free cells to disk (parquet for dataframes, JSON for
JSON-serializable values) and emits a "compiled" notebook in which
those cells are replaced with tiny artifact loaders. Cells whose
defs are no longer needed by anything in the output are elided
entirely; cells that depend on a runtime input or produce a
non-persistable value are emitted verbatim.

Re-running ``marimo build`` is incremental: artifacts are
content-addressed by a Merkle hash over the cell's source plus its
compilable ancestors, and stale artifacts are garbage-collected
after a successful build.

This module is the implementation behind the ``marimo build`` CLI
command.
"""

from __future__ import annotations

from marimo._build.build import BuildResult, build_notebook

__all__ = ["BuildResult", "build_notebook"]
