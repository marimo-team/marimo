# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
from collections import deque
from typing import TYPE_CHECKING
from uuid import uuid4

from marimo._cli.containers._create import OWNERSHIP_LABEL, create_args
from marimo._cli.containers._process import (
    COMMAND_TIMEOUT,
    error_detail,
    finish_process,
)
from marimo._cli.containers.engine import (
    Cancelled,
    CleanupComplete,
    ContainerIdentity,
    EngineFailure,
    StartFailure,
    WorkloadExit,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._cli.containers.engine import (
        CleanupResult,
        ContainerSession,
        LaunchRequest,
        SessionResult,
    )


class _DockerCompatibleEngine:
    def __init__(
        self, name: str, executable: str, *, relabel_mounts: bool = False
    ) -> None:
        self.name = name
        self.executable = executable
        self.relabel_mounts = relabel_mounts

    def run(self, *args: str, timeout: float | None = COMMAND_TIMEOUT) -> str:
        result = subprocess.run(
            [self.executable, *args],
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        return result.stdout.strip()

    def remove(self, container: str) -> str:
        return self.run("rm", "--force", container)

    def start(self, request: LaunchRequest) -> ContainerSession | StartFailure:
        try:
            self.run("info")
        except FileNotFoundError as error:
            return StartFailure(
                EngineFailure(
                    self.name,
                    "availability check",
                    f"{self.name} is not installed: {error}",
                )
            )
        except (OSError, subprocess.SubprocessError) as error:
            return StartFailure(
                EngineFailure(
                    self.name, "availability check", error_detail(error)
                )
            )
        except KeyboardInterrupt:
            return StartFailure(Cancelled())

        session = _DockerCompatibleSession(self, f"marimo-{uuid4().hex}")
        stage = "create"
        try:
            session.create(request)
            stage = "start"
            self.run("start", session.identity.container)
        except (OSError, subprocess.SubprocessError) as error:
            return StartFailure(
                session.failure(stage, error_detail(error)),
                session.close_after_start_failure(),
            )
        except KeyboardInterrupt:
            return StartFailure(
                Cancelled(), session.close_after_start_failure()
            )
        return session


class _DockerCompatibleSession:
    def __init__(self, engine: _DockerCompatibleEngine, name: str) -> None:
        self._engine = engine
        self._name = name
        self._id: str | None = None
        self._log_process: subprocess.Popen[str] | None = None
        self._result: SessionResult | None = None
        self._cleanup: CleanupComplete | None = None

    @property
    def identity(self) -> ContainerIdentity:
        return ContainerIdentity(self._engine.name, self._id or self._name)

    def failure(self, stage: str, detail: str) -> EngineFailure:
        return EngineFailure(
            self.identity.engine, stage, detail, self.identity.container
        )

    def create(self, request: LaunchRequest) -> None:
        self._id = self._engine.run(
            *create_args(
                request, self._name, relabel_mounts=self._engine.relabel_mounts
            ),
            timeout=None,
        )
        if not self._id:
            raise OSError("The engine did not return a container ID.")

    def logs(self) -> Iterator[str]:
        tail: deque[str] = deque(maxlen=10)
        try:
            process = subprocess.Popen(
                [
                    self._engine.executable,
                    "logs",
                    "--follow",
                    self.identity.container,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
            )
            self._log_process = process
            assert process.stdout is not None
            for line in process.stdout:
                tail.append(line)
                yield line
            status = process.wait()
            process.stdout.close()
            self._log_process = None
            if status:
                detail = "".join(tail).strip()
                self._result = self.failure(
                    "logs",
                    f"Engine exited with status {status}.\n{detail}".rstrip(),
                )
        except (OSError, subprocess.SubprocessError) as error:
            self._result = self.failure("logs", error_detail(error))

    def exit_result(self) -> SessionResult:
        if self._result is not None:
            return self._result

        result: SessionResult
        try:
            status = self._engine.run(
                "wait", self.identity.container, timeout=None
            )
        except (OSError, subprocess.SubprocessError) as error:
            result = self.failure("wait", error_detail(error))
        else:
            try:
                code = int(status)
                if code < 0:
                    raise ValueError(status)
            except ValueError:
                result = self.failure(
                    "wait", f"Invalid workload status: {status!r}"
                )
            else:
                result = WorkloadExit(code)
        self._result = result
        return result

    def _find_owned_container(self) -> str:
        return self._engine.run(
            "ps",
            "--all",
            "--quiet",
            "--no-trunc",
            "--filter",
            f"label={OWNERSHIP_LABEL}={self._name}",
        )

    def _remove(self) -> CleanupResult:
        try:
            container = self._id or self._find_owned_container()
        except (OSError, subprocess.SubprocessError) as error:
            return self.failure("find owned container", error_detail(error))
        if not container:
            return CleanupComplete("absent")

        try:
            if self._engine.remove(container):
                return CleanupComplete("removed")
            # Docker can return success with no output for a missing container.
            detail = "The engine did not report removal."
        except (OSError, subprocess.SubprocessError) as error:
            detail = error_detail(error)
        try:
            if not self._find_owned_container():
                return CleanupComplete("absent")
        except (OSError, subprocess.SubprocessError) as check_error:
            detail += f"\nCould not check container presence: {error_detail(check_error)}"
        return self.failure("remove", detail)

    def close(self) -> CleanupResult:
        if self._result is None:
            self._result = Cancelled()

        logs_failure = None
        try:
            if self._log_process is not None:
                finish_process(self._log_process)
                self._log_process = None
        except (OSError, subprocess.SubprocessError) as error:
            logs_failure = self.failure(
                "close log process", error_detail(error)
            )

        cleanup = self._cleanup or self._remove()
        if isinstance(cleanup, EngineFailure):
            if logs_failure is not None:
                return self.failure(
                    cleanup.stage, f"{cleanup.detail}\n{logs_failure}"
                )
            return cleanup
        self._cleanup = cleanup
        return logs_failure or cleanup

    def close_after_start_failure(self) -> CleanupResult | None:
        cleanup = self.close()
        if self._id is None and cleanup == CleanupComplete("absent"):
            return None
        return cleanup
