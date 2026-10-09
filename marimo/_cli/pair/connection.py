# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import msgspec

from marimo._cli.pair.client import PairInputError
from marimo._cli.pair.delivery import ProcessHandle
from marimo._utils.file_lock import file_lock
from marimo._utils.xdg import marimo_state_dir

if TYPE_CHECKING:
    from collections.abc import Iterator

_ID = re.compile(r"p1_[0-9a-f]{64}\Z")


def connection_identity(
    notebook: str, kind: str, conversation: str | None
) -> str:
    values = [
        "marimo-participant-v1",
        notebook,
        kind,
        "conversation" if conversation else "harness",
        conversation,
    ]
    raw = json.dumps(values, ensure_ascii=True, separators=(",", ":"))
    return "p1_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Connection(msgspec.Struct, frozen=True):
    version: Literal[1]
    identity: str
    notebook: str
    harness_kind: str
    harness_pid: int
    harness_start: float
    forwarder_pid: int
    forwarder_start: float
    created_at: float

    @property
    def forwarder(self) -> ProcessHandle:
        return ProcessHandle(self.forwarder_pid, self.forwarder_start)


class ConnectionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or marimo_state_dir() / "pair" / "connections-v1"

    def path(self, identity: str) -> Path:
        if _ID.fullmatch(identity) is None:
            raise PairInputError("Invalid Pair attachment identity.")
        return self.root / f"{identity}.json"

    def load(self, identity: str) -> Connection | None:
        try:
            raw = self.path(identity).read_bytes()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise PairInputError(
                "Could not read the Pair connection."
            ) from error
        try:
            record = msgspec.json.decode(raw, type=Connection)
        except msgspec.DecodeError as error:
            raise PairInputError(
                "Invalid Pair connection. Run connect again."
            ) from error
        if record.identity != identity:
            raise PairInputError("Mismatched Pair connection identity.")
        if record.harness_pid <= 0 or record.forwarder_pid <= 0:
            raise PairInputError("Invalid Pair process identity.")
        return record

    def select(
        self, notebook: str, *, kind: str, conversation: str | None
    ) -> Connection | None:
        if conversation is not None:
            record = self.load(
                connection_identity(notebook, kind, conversation)
            )
            if record is not None and (
                record.notebook != notebook or record.harness_kind != kind
            ):
                raise PairInputError("Mismatched Pair connection target.")
            return record
        candidates = []
        for path in self.root.glob("p1_*.json"):
            record = self.load(path.stem)
            if record is not None and record.notebook == notebook:
                candidates.append(record)
        if len(candidates) > 1:
            raise PairInputError(
                "Several Pair connections match. Run this command inside the harness."
            )
        return candidates[0] if candidates else None

    def save(self, record: Connection) -> None:
        try:
            self.root.mkdir(parents=True, mode=0o700, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                dir=self.root, suffix=".tmp"
            )
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(msgspec.json.encode(record))
                os.replace(temporary, self.path(record.identity))
            finally:
                Path(temporary).unlink(missing_ok=True)
        except OSError as error:
            raise PairInputError(
                "Could not save the Pair connection."
            ) from error

    def remove(self, record: Connection) -> None:
        # A replaced forwarder cannot delete the new owner's record.
        if self.load(record.identity) == record:
            self.path(record.identity).unlink(missing_ok=True)

    def stop(self, identity: str) -> None:
        """Stop and remove a connection while the caller holds its lock."""
        record = self.load(identity)
        if record is not None:
            record.forwarder.stop()
            self.remove(record)

    @contextmanager
    def locked(self, identity: str) -> Iterator[None]:
        self.root.mkdir(parents=True, mode=0o700, exist_ok=True)
        with file_lock(
            self.path(identity).with_suffix(".lock"), blocking=True
        ):
            yield
