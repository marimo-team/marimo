# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, TypedDict

# This file contains the schema for the notebook.
# It may be externally used and must be kept backwards compatible.
#
# We generate the OpenAPI schema using a marimo notebook: `python scripts/generate_schemas.py`
# We generate frontend types using `make fe-codegen`
# We check for backwards compatibility using a GitHub action: `.github/workflows/test_schemas.yaml`


class NotebookCellConfig(TypedDict, total=False):
    """Configuration for a notebook cell"""

    column: int | None
    disabled: bool | None
    hide_code: bool | None
    expand_output: bool | None


class NotebookCell(TypedDict):
    """Code cell specific structure"""

    id: str | None
    code: str | None
    code_hash: str | None
    name: str | None
    config: NotebookCellConfig


# Notebook metadata
class NotebookMetadata(TypedDict, total=False):
    """Metadata about the notebook"""

    marimo_version: str | None


# Main notebook structure
class NotebookV1(TypedDict):
    """Main notebook structure"""

    # The notebook format version
    version: Literal["1"]
    # Metadata about the notebook
    metadata: NotebookMetadata
    # The cells in the notebook
    cells: list[NotebookCell]
