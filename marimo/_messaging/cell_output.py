# Copyright 2023 Marimo. All rights reserved.
"""Specification of a cell's visual output
"""


from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Sequence, Union

from marimo._messaging.errors import Error


@dataclass
class CellOutput:
    # descriptive name about the kind of output: e.g., stdout, stderr, ...
    channel: str
    mimetype: str
    data: Union[str, Sequence[Error]]
    data_store: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())
