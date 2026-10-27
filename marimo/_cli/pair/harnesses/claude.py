# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import socket
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from marimo._cli.pair.client import PairError, PairInputError
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle

if TYPE_CHECKING:
    from collections.abc import Mapping


def _socket_exists(address: str) -> bool:
    try:
        info = Path(address).lstat()
        return stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid()
    except OSError:
        return False


class ClaudeHarness:
    """Discover a Claude Code session's native inbox and process owner."""

    kind = "claude"

    def identity(self, env: Mapping[str, str]) -> str | None:
        address = env.get("CLAUDE_CODE_MESSAGING_SOCKET")
        if address:
            return address
        if any(
            key in env
            for key in (
                "CLAUDE_PID",
                "CLAUDE_CODE_MESSAGING_SOCKET",
                "CLAUDE_CODE_MESSAGING_TOKEN",
            )
        ):
            raise PairInputError(
                "Claude Code did not export its inbox socket. "
                "Run this command inside a current Claude Code session."
            )
        return None

    def detect(
        self,
        env: Mapping[str, str],
        *,
        process: ProcessHandle | None = None,
    ) -> DeliveryTarget | None:
        import psutil

        address = self.identity(env)
        if address is None:
            return None
        self.check()
        if not _socket_exists(address):
            raise PairInputError(
                "The Claude Code inbox socket is unavailable."
            )
        token = env.get("CLAUDE_CODE_MESSAGING_TOKEN")
        if not token:
            raise PairInputError(
                "Claude Code did not export its inbox token. "
                "Run connect inside a current Claude Code session."
            )
        if process is not None:
            return DeliveryTarget(
                self.kind,
                address,
                "Claude Code",
                process=process,
                auth_token=token,
            )
        try:
            owner_pid = int(env.get("CLAUDE_PID", ""))
            if owner_pid <= 0:
                raise ValueError
        except ValueError as error:
            raise PairInputError(
                "Claude Code did not export a valid CLAUDE_PID. "
                "Run connect inside a current Claude Code session."
            ) from error
        try:
            for ancestor in psutil.Process().parents():
                if ancestor.pid == owner_pid:
                    return DeliveryTarget(
                        self.kind,
                        address,
                        "Claude Code",
                        process=ProcessHandle.capture(ancestor.pid),
                        auth_token=token,
                    )
        except psutil.Error as error:
            raise PairInputError(
                "Could not identify the Claude Code process."
            ) from error
        raise PairInputError(
            "Run connect inside a native Claude Code session."
        )

    def check(self) -> None:
        if os.name == "nt" or not hasattr(socket, "AF_UNIX"):
            raise PairInputError(
                "Claude Code inbox delivery requires macOS or Linux."
            )

    def open_inbox(self, target: DeliveryTarget) -> ClaudeInbox:
        return ClaudeInbox(target)


@dataclass(frozen=True)
class ClaudeInbox:
    """Send messages to one Claude socket while its owner and socket exist."""

    target: DeliveryTarget
    inbox_bytes: ClassVar[int] = 64 * 1024

    def send(self, text: str) -> None:
        if not self.target.auth_token:
            raise PairError("The Claude Code inbox token is unavailable.")
        # The socket and auth line are documented; the user frame is private.
        # Keep this encoding covered by a native Claude acceptance test.
        frames = [
            {"type": "auth", "token": self.target.auth_token},
            {"type": "user", "message": {"role": "user", "content": text}},
        ]
        data = "".join(json.dumps(frame) + "\n" for frame in frames).encode()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as inbox:
                inbox.settimeout(5)
                inbox.connect(self.target.address)
                inbox.sendall(data)
                inbox.shutdown(socket.SHUT_WR)
        except (OSError, ValueError) as error:
            raise PairError(
                "Could not deliver the message to Claude Code. "
                "Check that its inbox is available and inbound messages are allowed."
            ) from error

    def alive(self) -> bool:
        return (
            self.target.process is not None
            and self.target.process.alive()
            and _socket_exists(self.target.address)
        )
