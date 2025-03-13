# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict, Union


# Base types for extensibility
class BaseDict(TypedDict, total=False):
    """Base dictionary allowing additional fields"""

    pass


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


class Cell(BaseDict):
    """Code cell specific structure"""

    id: str
    code_hash: Optional[str]
    outputs: list[OutputType]
    console: list[StreamOutput]

    # We don't need to store code or cell config
    # since that exists in the notebook.py itself


# Notebook metadata
class NotebookMetadata(BaseDict):
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
    metadata: NotebookMetadata
    # The cells in the notebook
    cells: list[Cell]

    # In future, we may want to add
    # - variables
    # - datasets


VERSION = "1"
