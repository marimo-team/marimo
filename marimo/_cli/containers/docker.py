# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
from collections import deque
from typing import TYPE_CHECKING
from uuid import uuid4

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

_COMMAND_TIMEOUT = 10
_OWNERSHIP_LABEL = "io.marimo.session"


def _error_detail(error: OSError | subprocess.SubprocessError) -> str:
    if isinstance(
        error, (subprocess.CalledProcessError, subprocess.TimeoutExpired)
    ):
        stderr = error.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        if stderr and stderr.strip():
            return stderr.strip()
    return str(error)


def _docker(*args: str, timeout: float | None = _COMMAND_TIMEOUT) -> str:
    result = subprocess.run(
        ["docker", *args],
        check=True,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
    )
    return result.stdout.strip()


class DockerEngine:
    def start(self, request: LaunchRequest) -> ContainerSession | StartFailure:
        try:
            _docker("info", "--format", "{{.ServerVersion}}")
        except FileNotFoundError as error:
            return StartFailure(
                EngineFailure(
                    "Docker",
                    "availability check",
                    f"Docker is not installed: {error}",
                )
            )
        except (OSError, subprocess.SubprocessError) as error:
            return StartFailure(
                EngineFailure(
                    "Docker", "availability check", _error_detail(error)
                )
            )
        except KeyboardInterrupt:
            return StartFailure(Cancelled())

        session = _DockerSession(f"marimo-{uuid4().hex}")
        stage = "create"
        try:
            session.create(request)
            stage = "start"
            _docker("start", session.identity.container)
        except (OSError, subprocess.SubprocessError) as error:
            return StartFailure(
                session.failure(stage, _error_detail(error)),
                session.close_after_start_failure(),
            )
        except KeyboardInterrupt:
            return StartFailure(
                Cancelled(), session.close_after_start_failure()
            )
        return session


class _DockerSession:
    def __init__(self, name: str) -> None:
        self._name = name
        self._id: str | None = None
        self._log_process: subprocess.Popen[str] | None = None
        self._result: SessionResult | None = None
        self._cleanup: CleanupComplete | None = None

    @property
    def identity(self) -> ContainerIdentity:
        return ContainerIdentity("Docker", self._id or self._name)

    def failure(self, stage: str, detail: str) -> EngineFailure:
        return EngineFailure(
            self.identity.engine, stage, detail, self.identity.container
        )

    def create(self, request: LaunchRequest) -> None:
        args = [
            "create",
            "--name",
            self._name,
            "--label",
            f"{_OWNERSHIP_LABEL}={self._name}",
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
        self._id = _docker(*args, request.image, *request.argv, timeout=None)
        if not self._id:
            raise OSError("Docker did not return a container ID.")

    def logs(self) -> Iterator[str]:
        tail: deque[str] = deque(maxlen=10)
        try:
            process = subprocess.Popen(
                ["docker", "logs", "--follow", self.identity.container],
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
                    f"Docker exited with status {status}.\n{detail}".rstrip(),
                )
        except (OSError, subprocess.SubprocessError) as error:
            self._result = self.failure("logs", _error_detail(error))

    def exit_result(self) -> SessionResult:
        if self._result is not None:
            return self._result

        result: SessionResult
        try:
            status = _docker("wait", self.identity.container, timeout=None)
        except (OSError, subprocess.SubprocessError) as error:
            result = self.failure("wait", _error_detail(error))
        else:
            try:
                result = WorkloadExit(int(status))
            except ValueError:
                result = self.failure(
                    "wait", f"Invalid workload status: {status!r}"
                )
        self._result = result
        return result

    def _finish_logs(self) -> None:
        process = self._log_process
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=_COMMAND_TIMEOUT)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=_COMMAND_TIMEOUT)
        if process.stdout is not None:
            process.stdout.close()
        self._log_process = None

    def _find_owned_container(self) -> str:
        return _docker(
            "ps",
            "--all",
            "--quiet",
            "--no-trunc",
            "--filter",
            f"label={_OWNERSHIP_LABEL}={self._name}",
        )

    def _remove(self) -> CleanupResult:
        try:
            container = self._id or self._find_owned_container()
        except (OSError, subprocess.SubprocessError) as error:
            return self.failure("find owned container", _error_detail(error))
        if not container:
            return CleanupComplete("absent")

        try:
            if _docker("rm", "--force", container):
                return CleanupComplete("removed")
            # Docker can return success with no output for a missing container.
            detail = "Docker did not report removal."
        except (OSError, subprocess.SubprocessError) as error:
            detail = _error_detail(error)
        try:
            if not self._find_owned_container():
                return CleanupComplete("absent")
        except (OSError, subprocess.SubprocessError) as check_error:
            detail += f"\nCould not check container presence: {_error_detail(check_error)}"
        return self.failure("remove", detail)

    def close(self) -> CleanupResult:
        if self._result is None:
            self._result = Cancelled()

        logs_failure = None
        try:
            self._finish_logs()
        except (OSError, subprocess.SubprocessError) as error:
            logs_failure = self.failure(
                "close log process", _error_detail(error)
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
