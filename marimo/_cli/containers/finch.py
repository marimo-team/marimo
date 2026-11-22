# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._cli.containers._docker_compatible import _DockerCompatibleEngine


class FinchEngine(_DockerCompatibleEngine):
    def __init__(self, executable: str = "finch") -> None:
        super().__init__("Finch", executable)
