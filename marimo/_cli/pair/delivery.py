# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class ProcessHandle:
    pid: int
    started: float

    @classmethod
    def capture(cls, pid: int) -> ProcessHandle:
        import psutil

        return cls(pid, psutil.Process(pid).create_time())

    def alive(self) -> bool:
        import psutil

        try:
            process = psutil.Process(self.pid)
            return (
                process.create_time() == self.started
                and process.is_running()
                and process.status() != psutil.STATUS_ZOMBIE
            )
        except psutil.Error:
            return False

    def stop(self) -> None:
        import psutil

        try:
            process = psutil.Process(self.pid)
            if process.create_time() != self.started:
                return
            process.terminate()
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        except psutil.NoSuchProcess:
            pass
        except psutil.Error as error:
            from marimo._cli.pair.client import PairError

            raise PairError(
                "Could not stop the Pair forwarder process."
            ) from error


@dataclass(frozen=True)
class DeliveryTarget:
    kind: str
    address: str
    label: str
    process: ProcessHandle | None = None


class HarnessAdapter(Protocol):
    kind: str
    inbox_bytes: int

    def identity(self, env: Mapping[str, str]) -> str | None: ...

    def detect(self, env: Mapping[str, str]) -> DeliveryTarget | None: ...

    def check(self) -> None: ...

    def send(self, target: DeliveryTarget, text: str) -> None: ...

    def alive(self, target: DeliveryTarget) -> bool: ...
