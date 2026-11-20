# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class PortMapping:
    host: int
    container: int


@dataclass(frozen=True)
class BindMount:
    source: str
    target: str
    read_only: bool = False


@dataclass(frozen=True)
class LaunchRequest:
    image: str
    argv: tuple[str, ...]
    environment: tuple[tuple[str, str], ...] = ()
    working_directory: str | None = None
    ports: tuple[PortMapping, ...] = ()
    mounts: tuple[BindMount, ...] = ()


@dataclass(frozen=True)
class ContainerIdentity:
    engine: str
    container: str


@dataclass(frozen=True)
class EngineFailure:
    engine: str
    stage: str
    detail: str
    container: str | None = None

    def __str__(self) -> str:
        resource = f" for container {self.container}" if self.container else ""
        return f"{self.engine} {self.stage} failed{resource}: {self.detail}"


@dataclass(frozen=True)
class WorkloadExit:
    status: int


@dataclass(frozen=True)
class Cancelled:
    pass


@dataclass(frozen=True)
class CleanupComplete:
    state: Literal["removed", "absent"]


SessionResult = WorkloadExit | Cancelled | EngineFailure
CleanupResult = CleanupComplete | EngineFailure


@dataclass(frozen=True)
class StartFailure:
    result: EngineFailure | Cancelled
    cleanup: CleanupResult | None = None


class ContainerSession(Protocol):
    @property
    def identity(self) -> ContainerIdentity: ...

    def logs(self) -> Iterator[str]: ...

    def exit_result(self) -> SessionResult: ...

    def close(self) -> CleanupResult: ...


class ContainerEngine(Protocol):
    def start(
        self, request: LaunchRequest
    ) -> ContainerSession | StartFailure: ...
