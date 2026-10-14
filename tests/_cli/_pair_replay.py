# Copyright 2026 Marimo. All rights reserved.
"""Subprocess driver for a controlled interruption of a real host stream."""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import msgspec

from marimo._cli.pair import forwarder
from marimo._cli.pair.client import EventStream, open_events
from marimo._cli.pair.delivery import DeliveryTarget
from marimo._cli.pair.forwarder import ForwarderConfig

if TYPE_CHECKING:
    from collections.abc import Mapping


class RecordingAdapter:
    kind = "test"
    inbox_bytes = 8192

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def identity(self, _env: Mapping[str, str]) -> None:
        return None

    def detect(self, _env: Mapping[str, str]) -> None:
        return None

    def check(self) -> None:
        pass

    def alive(self, target: DeliveryTarget) -> bool:
        return target.process is not None and target.process.alive()

    def send(self, _target: DeliveryTarget, text: str) -> None:
        with (self.directory / "inbox.jsonl").open("a") as output:
            output.write(json.dumps({"message": text}) + "\n")


def main() -> None:
    directory = Path(sys.argv[1])
    config = msgspec.json.decode(sys.stdin.read(), type=ForwarderConfig)
    calls = 0

    def controlled_events(
        *,
        url: str,
        notebook: str,
        token: str | None,
        identity: str,
        name: str,
        cursor: str | None = None,
    ) -> EventStream:
        nonlocal calls
        calls += 1
        if calls == 2:
            (directory / "reconnecting.json").write_text(
                json.dumps({"cursor": cursor})
            )
            while not (directory / "resume").exists():
                time.sleep(0.01)
        response = open_events(
            url=url,
            notebook=notebook,
            token=token,
            identity=identity,
            name=name,
            cursor=cursor,
        )
        if calls == 1:

            def drop() -> None:
                while not (directory / "drop").exists():
                    time.sleep(0.01)
                response.socket.shutdown(socket.SHUT_RDWR)

            threading.Thread(target=drop, daemon=True).start()
        return response

    with patch.object(forwarder, "open_events", side_effect=controlled_events):
        forwarder.run_forwarder(
            config,
            RecordingAdapter(directory),
            ready=lambda: print("attached", flush=True),
        )


if __name__ == "__main__":
    main()
