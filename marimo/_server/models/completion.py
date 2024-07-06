# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class AiCompletionRequest:
    prompt: str
    include_other_code: str
    code: str
    language: Literal["python", "markdown", "sql"] = "python"
