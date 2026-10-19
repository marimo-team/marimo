# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from marimo._cli.pair.client import PairError, PairInputError
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle
from marimo._utils.platform import is_windows

if TYPE_CHECKING:
    from collections.abc import Mapping


class CodexHarness:
    """Discover Codex conversations and check shared-daemon support."""

    kind = "codex"

    @staticmethod
    def executable() -> str:
        # Batch shims can interpret message text as shell syntax on Windows.
        return "codex.exe" if is_windows() else "codex"

    def detect(
        self,
        env: Mapping[str, str],
        *,
        process: ProcessHandle | None = None,
    ) -> DeliveryTarget | None:
        import psutil

        address = self.identity(env)
        if not address:
            return None
        if process is not None:
            self.check()
            return DeliveryTarget(self.kind, address, "Codex", process=process)
        owner = None
        try:
            for ancestor in psutil.Process().parents():
                if Path(ancestor.name()).stem.lower().startswith("codex"):
                    arguments = ancestor.cmdline()
                    if "--no-daemon" in arguments or any(
                        argument.endswith("stdio://") for argument in arguments
                    ):
                        raise PairInputError(
                            "This Codex session does not use the shared daemon. "
                            "Run connect inside a native Codex daemon session."
                        )
                    owner = ProcessHandle.capture(ancestor.pid)
                    break
        except psutil.Error as error:
            raise PairInputError(
                "Could not identify the Codex process."
            ) from error
        if owner is None:
            raise PairInputError("Run connect inside a native Codex session.")
        self.check()
        return DeliveryTarget(self.kind, address, "Codex", process=owner)

    def identity(self, env: Mapping[str, str]) -> str | None:
        address = env.get("CODEX_SESSION_ID") or env.get("CODEX_THREAD_ID")
        if not address:
            if "CODEX_SESSION_ID" in env or "CODEX_THREAD_ID" in env:
                raise PairInputError(
                    "Codex did not export a conversation ID. "
                    "Run this command inside a native Codex session."
                )
            return None
        return address

    def check(self) -> None:
        try:
            result = subprocess.run(
                [self.executable(), "app-server", "daemon", "version"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            info = json.loads(result.stdout)
            running = (
                isinstance(info, dict) and info.get("status") == "running"
            )
            if result.returncode == 0 and running:
                queue_help = subprocess.run(
                    [self.executable(), "queue", "--help"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                if queue_help.returncode != 0:
                    raise PairInputError(
                        "Install a Codex CLI with queue support."
                    )
        except (OSError, subprocess.TimeoutExpired, ValueError) as error:
            raise PairInputError(
                "Could not check the Codex daemon. "
                "Install a Codex CLI with queue support."
            ) from error
        if result.returncode != 0 or not running:
            raise PairInputError(
                "The Codex daemon is not running. "
                "Run codex app-server daemon start, then reconnect."
            )

    def open_inbox(self, target: DeliveryTarget) -> CodexInbox:
        return CodexInbox(target, self.executable())


@dataclass(frozen=True)
class CodexInbox:
    """Queue messages for one Codex conversation while its owner is alive."""

    target: DeliveryTarget
    executable: str
    # Leave room for the executable and options within Windows command limits.
    inbox_bytes: ClassVar[int] = 8 * 1024

    def send(self, text: str) -> None:
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "queue",
                    "--thread",
                    self.target.address,
                    "--message",
                    text,
                ],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            raise PairError(
                "Could not deliver the message to Codex."
            ) from error
        if result.returncode != 0:
            raise PairError(
                "Codex rejected the message. Check that the conversation "
                "uses the shared daemon and supports codex queue."
            )

    def alive(self) -> bool:
        return self.target.process is not None and self.target.process.alive()
