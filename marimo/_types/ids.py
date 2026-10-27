# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import NewType

CellId_t = NewType("CellId_t", str)

UIElementId = NewType("UIElementId", str)

# Session routing key, which may change when a browser resumes.
SessionId = NewType("SessionId", str)

# Internal identity for one session lifetime, preserved across reconnects and
# notebook renames. A replacement session gets a fresh ID even for the same
# notebook. Separate from SessionId and the creation key (initialization_id).
StableSessionId = NewType("StableSessionId", str)

ConsumerId = NewType("ConsumerId", str)

VariableName = NewType("VariableName", str)

RequestId = NewType("RequestId", str)

# AnyWidget model id
WidgetModelId = NewType("WidgetModelId", str)
