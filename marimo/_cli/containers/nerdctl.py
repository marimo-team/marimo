# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._cli.containers._docker_compatible import _DockerCompatibleEngine


class NerdctlEngine(_DockerCompatibleEngine):
    def __init__(self, executable: str = "nerdctl") -> None:
        super().__init__("nerdctl", executable)
