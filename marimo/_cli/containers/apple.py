# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
from collections import Counter, deque
from typing import TYPE_CHECKING
from uuid import uuid4

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

_NAME = "Apple container"
_DIAGNOSTIC_LINES = 10


class AppleContainerEngine:
    def __init__(self, executable: str = "container") -> None:
        self._executable = executable

    def start(self, request: LaunchRequest) -> ContainerSession | StartFailure:
        session = _AppleSession(self._executable, f"marimo-{uuid4().hex}")
        try:
            session.run("list", "--all", "--quiet")
        except (OSError, subprocess.SubprocessError) as error:
            return StartFailure(
                EngineFailure(_NAME, "availability check", error_detail(error))
            )
        except KeyboardInterrupt:
            return StartFailure(Cancelled())

        stage = "create"
        try:
            session.create(request)
            stage = "start"
            session.attach()
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


class _AppleSession:
    def __init__(self, executable: str, container: str) -> None:
        self._executable = executable
        self._container = container
        self._created = False
        self._process: subprocess.Popen[str] | None = None
        self._tail: deque[str] = deque(maxlen=_DIAGNOSTIC_LINES)
        self._result: SessionResult | None = None
        self._cleanup: CleanupComplete | None = None

    @property
    def identity(self) -> ContainerIdentity:
        return ContainerIdentity(_NAME, self._container)

    def failure(self, stage: str, detail: str) -> EngineFailure:
        return EngineFailure(_NAME, stage, detail, self._container)

    def run(self, *args: str, timeout: float | None = COMMAND_TIMEOUT) -> str:
        result = subprocess.run(
            [self._executable, *args],
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        return result.stdout

    def create(self, request: LaunchRequest) -> None:
        args = [
            "create",
            "--name",
            self._container,
            "--label",
            f"io.marimo.session={self._container}",
        ]
        for mapping in request.ports:
            args.extend(("--publish", f"{mapping.host}:{mapping.container}"))
        for key, value in request.environment:
            args.extend(("--env", f"{key}={value}"))
        if request.working_directory is not None:
            args.extend(("--workdir", request.working_directory))
        for mount in request.mounts:
            mode = ":ro" if mount.read_only else ""
            args.extend(("--volume", f"{mount.source}:{mount.target}{mode}"))
        self.run(*args, request.image, *request.argv, timeout=None)
        self._created = True

    def attach(self) -> None:
        self._process = subprocess.Popen(
            [self._executable, "start", "--attach", self._container],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            start_new_session=True,
        )

    def logs(self) -> Iterator[str]:
        if self._process is None or self._process.stdout is None:
            return
        try:
            for line in self._process.stdout:
                self._tail.append(line)
                yield line
        except OSError as error:
            self._result = self.failure("logs", error_detail(error))

    def _attached_result(self, status: int) -> SessionResult:
        if status < 0:
            return self.failure(
                "start", f"The attached process ended with signal {-status}."
            )
        if status not in (1, 64):
            return WorkloadExit(status)

        diagnostics = Counter(
            line.rstrip("\n")
            for line in self._tail
            if line.startswith("Error:")
        )
        if not diagnostics:
            return WorkloadExit(status)

        # The CLI shares stderr with the workload. Engine errors appear only
        # in the attached output, while workload output also appears in logs.
        try:
            workload = self.run(
                "logs", "-n", str(_DIAGNOSTIC_LINES * 2), self._container
            )
        except (OSError, subprocess.SubprocessError) as error:
            return self.failure(
                "start",
                f"{''.join(self._tail).strip()}\n"
                f"Could not check workload logs: {error_detail(error)}",
            )
        if diagnostics - Counter(workload.splitlines()):
            return self.failure("start", "".join(self._tail).strip())
        return WorkloadExit(status)

    def exit_result(self) -> SessionResult:
        if self._result is not None:
            return self._result
        process = self._process
        if process is None:
            self._result = self.failure("start", "No attached process.")
            return self._result

        for _ in self.logs():
            pass
        if self._result is not None:
            return self._result
        try:
            result = self._attached_result(process.wait())
        except (OSError, subprocess.SubprocessError) as error:
            result = self.failure("start", error_detail(error))
        self._result = result
        return result

    def _exists(self) -> bool:
        return (
            self._container
            in self.run("list", "--all", "--quiet").splitlines()
        )

    def _remove(self) -> CleanupResult:
        try:
            if not self._created and not self._exists():
                return CleanupComplete("absent")
        except (OSError, subprocess.SubprocessError) as error:
            return self.failure("find owned container", error_detail(error))

        try:
            removed = self.run("delete", "--force", self._container)
            if self._container in removed.splitlines():
                return CleanupComplete("removed")
            detail = "The engine did not report removal."
        except (OSError, subprocess.SubprocessError) as error:
            detail = error_detail(error)
        try:
            if not self._exists():
                return CleanupComplete("absent")
        except (OSError, subprocess.SubprocessError) as error:
            detail += (
                f"\nCould not check container presence: {error_detail(error)}"
            )
        return self.failure("remove", detail)

    def close(self) -> CleanupResult:
        if self._result is None:
            self._result = Cancelled()
        process_error = None
        try:
            cleanup = self._cleanup or self._remove()
        finally:
            try:
                if self._process is not None:
                    finish_process(self._process)
                    self._process = None
            except (OSError, subprocess.SubprocessError) as error:
                process_error = self.failure(
                    "close attached process", error_detail(error)
                )
        if isinstance(cleanup, EngineFailure):
            if process_error is not None:
                return self.failure(
                    cleanup.stage, f"{cleanup.detail}\n{process_error}"
                )
            return cleanup
        self._cleanup = cleanup
        return process_error or cleanup

    def close_after_start_failure(self) -> CleanupResult | None:
        cleanup = self.close()
        if not self._created and cleanup == CleanupComplete("absent"):
            return None
        return cleanup
