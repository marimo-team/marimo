# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._schemas.common import BaseDict

# This file contains the schema for the notebook.
# It may be externally used and must be kept backwards compatible.
#
# We generate the OpenAPI schema using a marimo notebook: `python scripts/generate_schemas.py`
# We generate frontend types using `make fe-codegen`
# We check for backwards compatibility using a GitHub action: `.github/workflows/test_schemas.yaml`


class NotebookCellConfig(BaseDict):
    """Configuration for a notebook cell"""

    column: Optional[int]
    disabled: Optional[bool]
    hide_code: Optional[bool]


class NotebookCell(BaseDict):
    """Code cell specific structure"""

    id: str
    code: Optional[str]
    name: Optional[str]
    config: NotebookCellConfig


# Notebook metadata
class NotebookMetadata(BaseDict):
    """Metadata about the notebook"""

    marimo_version: Optional[str]


# Main notebook structure
class NotebookV1(BaseDict):
    """Main notebook structure"""

    # The notebook format version
    version: str
    # Metadata about the notebook
    metadata: NotebookMetadata
    # The cells in the notebook
    cells: list[NotebookCell]
