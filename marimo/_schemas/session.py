# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from marimo._messaging.mimetypes import KnownMimeType
from marimo._schemas.common import BaseDict

# This file contains the schema for the notebook session.
# It may be externally used and must be kept backwards compatible.
#
# We generate the OpenAPI schema using a marimo notebook: `python scripts/generate_schemas.py`
# We generate frontend types using `make fe-codegen`
# We check for backwards compatibility using a GitHub action: `.github/workflows/test_schemas.yaml`


# Metadata types
class TimeMetadata(BaseDict):
    started: Optional[str]
    completed: Optional[str]
    duration: Optional[float]


# Output types
class StreamOutput(BaseDict):
    type: Literal["stream"]
    name: Literal["stdout", "stderr"]
    text: str


class StreamMediaOutput(BaseDict):
    type: Literal["stream"]
    name: Literal["media"]
    data: str
    mimetype: KnownMimeType


class ErrorOutput(BaseDict):
    type: Literal["error"]
    ename: str
    evalue: str
    traceback: list[str]


class DataOutput(BaseDict):
    type: Literal["data"]
    data: dict[str, Any]  # MIME-type bundles


# Union of all possible output types
OutputType = Union[
    ErrorOutput,
    DataOutput,
    # Dict[str, Any],  # For future output types, forwards-compatible
]

ConsoleType = Union[
    StreamOutput,
    StreamMediaOutput,
]


class Cell(BaseDict):
    """Code cell specific structure"""

    id: str
    code_hash: Optional[str]
    outputs: list[OutputType]
    console: list[ConsoleType]

    # We don't need to store code or cell config
    # since that exists in the notebook.py itself


# Notebook session metadata
class NotebookSessionMetadata(BaseDict):
    """Metadata about the notebook"""

    marimo_version: Optional[str]

    # We don't need to store AppConfig
    # since that exists in the notebook.py itself


# Main notebook structure
class NotebookSessionV1(BaseDict):
    """Main notebook structure"""

    # The notebook format version
    version: str
    # Metadata about the notebook
    metadata: NotebookSessionMetadata
    # The cells in the notebook
    cells: list[Cell]

    # In future, we may want to add
    # - variables
    # - datasets


VERSION = "1"
