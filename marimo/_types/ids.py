# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import NewType

CellId_t = NewType("CellId_t", str)

UIElementId = NewType("UIElementId", str)

# Session routing key, which may change when a browser resumes.
SessionId = NewType("SessionId", str)

# Identity of a session, preserved across reconnects, notebook renames, and
# kernel restarts: whoever creates a session chooses it, and a kernel that
# continues an earlier one is given the same id. Separate from SessionId and
# the creation key (initialization_id). A host publishes it as the RuntimeId.
StableSessionId = NewType("StableSessionId", str)

ConsumerId = NewType("ConsumerId", str)

VariableName = NewType("VariableName", str)

RequestId = NewType("RequestId", str)

# AnyWidget model id
WidgetModelId = NewType("WidgetModelId", str)
