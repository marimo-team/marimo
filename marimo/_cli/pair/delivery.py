# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class ProcessHandle:
    """A process identified by both PID and start time to detect PID reuse."""

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
            if (
                process.create_time() != self.started
                or not process.is_running()
                or process.status() == psutil.STATUS_ZOMBIE
            ):
                return
            process.terminate()
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                if process.status() == psutil.STATUS_ZOMBIE:
                    return
                process.kill()
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    if process.status() != psutil.STATUS_ZOMBIE:
                        raise
        except psutil.NoSuchProcess:
            pass
        except psutil.Error as error:
            from marimo._cli.pair.client import PairError

            raise PairError(
                "Could not stop the Pair forwarder process."
            ) from error


@dataclass(frozen=True)
class DeliveryTarget:
    """An inbox address and the process that controls its connection lifetime.

    Credentials stay in memory and are excluded from diagnostic representations.
    """

    kind: str
    address: str
    label: str
    process: ProcessHandle | None = None
    auth_token: str | None = field(default=None, repr=False)


class Harness(Protocol):
    """Discover a ready harness destination and bind its inbox.

    Each adapter checks readiness during detection, before returning a target.
    """

    kind: str

    def identity(self, env: Mapping[str, str]) -> str | None: ...

    def detect(
        self,
        env: Mapping[str, str],
        *,
        process: ProcessHandle | None = None,
    ) -> DeliveryTarget | None: ...

    def check(self) -> None: ...

    def open_inbox(self, target: DeliveryTarget) -> Inbox: ...


class Inbox(Protocol):
    """Delivery and lifetime checks for one already-selected conversation."""

    @property
    def inbox_bytes(self) -> int: ...

    def send(self, text: str) -> None: ...

    def alive(self) -> bool: ...
