# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._cli.containers._docker_compatible import _DockerCompatibleEngine


class PodmanEngine(_DockerCompatibleEngine):
    def __init__(self, executable: str = "podman") -> None:
        super().__init__("Podman", executable, relabel_mounts=True)

    def remove(self, container: str) -> str:
        return self.run("rm", "--force", "--time", "0", container)
