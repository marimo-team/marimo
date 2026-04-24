# Copyright 2026 Marimo. All rights reserved.
"""ZMQ connection management for IPC between an app host and its process."""

from __future__ import annotations

import dataclasses
import os
from typing import TYPE_CHECKING

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._session.app_host.commands import AppHostArgs

if TYPE_CHECKING:
    import zmq

_BIND_ADDR = "tcp://127.0.0.1"


@dataclasses.dataclass
class AppHostConnection:
    """Manages all ZeroMQ sockets for an AppHost."""

    context: zmq.Context[zmq.Socket[bytes]]

    # PUSH — single frame: encode_mgmt_command(MgmtCommand)
    mgmt: zmq.Socket[bytes]
    # PULL — single frame: decode_mgmt_response(bytes) -> MgmtResponse
    response: zmq.Socket[bytes]

    # TODO(akshayka): Consider moving to something less fragile than pickle
    # PUSH — 3-frame multipart: [session_id, channel, pickle(payload)]
    cmd: zmq.Socket[bytes]
    # PULL — 2-frame multipart: [session_id, pickle(KernelMessage | KernelExited)]
    stream: zmq.Socket[bytes]

    @classmethod
    def create(
        cls, file_path: str, log_level: int | None = None
    ) -> tuple[AppHostConnection, AppHostArgs]:
        """Bind all sockets, return connection and args for subprocess."""
        import zmq

        if log_level is None:
            log_level = GLOBAL_SETTINGS.LOG_LEVEL

        context = zmq.Context()
        try:
            mgmt = context.socket(zmq.PUSH)
            mgmt_port = mgmt.bind_to_random_port(_BIND_ADDR)

            response = context.socket(zmq.PULL)
            response_port = response.bind_to_random_port(_BIND_ADDR)

            cmd = context.socket(zmq.PUSH)
            cmd_port = cmd.bind_to_random_port(_BIND_ADDR)

            stream = context.socket(zmq.PULL)
            stream_port = stream.bind_to_random_port(_BIND_ADDR)
        except Exception:
            context.destroy(linger=0)
            raise

        conn = cls(
            context=context,
            mgmt=mgmt,
            response=response,
            cmd=cmd,
            stream=stream,
        )

        args = AppHostArgs(
            mgmt_addr=f"{_BIND_ADDR}:{mgmt_port}",
            response_addr=f"{_BIND_ADDR}:{response_port}",
            cmd_addr=f"{_BIND_ADDR}:{cmd_port}",
            stream_addr=f"{_BIND_ADDR}:{stream_port}",
            file_path=file_path,
            log_level=log_level,
            parent_pid=os.getpid(),
        )

        return conn, args

    def close(self) -> None:
        """Close all sockets and destroy context."""
        self.mgmt.close(linger=0)
        self.response.close(linger=0)
        self.cmd.close(linger=0)
        self.stream.close(linger=0)
        self.context.destroy(linger=0)
