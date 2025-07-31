# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import NewType

CellId_t = NewType("CellId_t", str)

UIElementId = NewType("UIElementId", str)

SessionId = NewType("SessionId", str)

ConsumerId = NewType("ConsumerId", str)

VariableName = NewType("VariableName", str)

RequestId = NewType("RequestId", str)

# AnyWidget model id
WidgetModelId = NewType("WidgetModelId", str)
