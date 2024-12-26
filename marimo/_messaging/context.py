# Copyright 2024 Marimo. All rights reserved.
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Optional

RunId_t = str
RUN_ID_CTX = ContextVar[Optional[RunId_t]]("run_id")


@dataclass
class run_id_context:
    """Context manager for setting and unsetting the run ID."""

    run_id: RunId_t

    def __init__(self) -> None:
        self.run_id = str(uuid.uuid4())

    def __enter__(self) -> None:
        self.token = RUN_ID_CTX.set(self.run_id)

    def __exit__(self, *_: Any) -> None:
        RUN_ID_CTX.reset(self.token)
