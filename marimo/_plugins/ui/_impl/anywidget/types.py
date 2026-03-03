# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, NewType, Union

# AnyWidget model id
WidgetModelId = NewType("WidgetModelId", str)

# Buffer paths
BufferPaths = list[list[Union[str, int]]]

# Widget model state
WidgetModelState = dict[str, Any]

# Widget model state without buffers
WidgetModelStateWithoutBuffers = dict[str, Any]
