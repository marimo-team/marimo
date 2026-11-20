# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._cli.containers.apple import AppleContainerEngine
from marimo._cli.containers.docker import DockerEngine
from marimo._cli.containers.finch import FinchEngine
from marimo._cli.containers.nerdctl import NerdctlEngine
from marimo._cli.containers.podman import PodmanEngine

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._cli.containers.engine import ContainerEngine


_ENGINES: dict[str, Callable[[str], ContainerEngine]] = {
    "docker": DockerEngine,
    "podman": PodmanEngine,
    "nerdctl": NerdctlEngine,
    "finch": FinchEngine,
    "container": AppleContainerEngine,
}


def resolve_engine(executable: str) -> ContainerEngine:
    path = Path(executable)
    name = path.name
    if os.name == "nt":
        name = name.lower()
        if path.suffix.lower() in {".exe", ".com", ".cmd", ".bat"}:
            name = path.stem.lower()

    factory = _ENGINES.get(name)
    if factory is None:
        return DockerEngine(executable, name=executable)
    return factory(executable)
