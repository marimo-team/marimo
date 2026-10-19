# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import stat
import tempfile
import time
import uuid
from pathlib import Path

from marimo._cli.pair.client import PairError

_PREFIX = "marimo-pair-messages-"
_MAX_AGE = 24 * 60 * 60


class AgentMessageFiles:
    """Preserve oversized inbox payloads in private JSON files.

    Files outlive the connection so agents can read them after detach.
    """

    def __init__(self) -> None:
        self.directory: Path | None = None

    def write(self, payload: object) -> Path:
        try:
            if self.directory is None or not self.directory.exists():
                self.directory = Path(
                    tempfile.mkdtemp(prefix=_PREFIX)
                ).resolve()
            info = self.directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or (
                hasattr(os, "getuid") and info.st_uid != os.getuid()
            ):
                raise ValueError("The message directory is no longer owned.")
            path = self.directory / f"{uuid.uuid4().hex}.json"
            descriptor = os.open(
                path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            try:
                with os.fdopen(
                    descriptor, "w", encoding="utf-8", newline="\n"
                ) as stream:
                    json.dump(payload, stream, ensure_ascii=True)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
            return path
        except (OSError, ValueError) as error:
            raise PairError(
                "Could not save the complete agent message. No shortened message was sent."
            ) from error

    @staticmethod
    def cleanup(*, now: float | None = None) -> None:
        cutoff = (time.time() if now is None else now) - _MAX_AGE
        for directory in Path(tempfile.gettempdir()).glob(f"{_PREFIX}*"):
            try:
                if directory.is_symlink() or not directory.is_dir():
                    continue
                if (
                    hasattr(os, "getuid")
                    and directory.stat().st_uid != os.getuid()
                ):
                    continue
                directory_mtime = directory.stat().st_mtime
                for path in directory.iterdir():
                    if (
                        not path.is_symlink()
                        and len(path.stem) == 32
                        and all(
                            char in "0123456789abcdef" for char in path.stem
                        )
                        and path.suffix == ".json"
                        and path.is_file()
                        and path.stat().st_mtime < cutoff
                    ):
                        path.unlink()
                if directory_mtime < cutoff:
                    directory.rmdir()
            except OSError:
                continue


def inbox_message(
    payload: object, *, notebook: str, budget: int, files: AgentMessageFiles
) -> str:
    prefix = f"Agent message from marimo (notebook {notebook}).\n"
    text = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=True)
    )
    # NUL cannot travel in a subprocess argument. Preserve its JSON spelling.
    text = text.replace("\0", "\\u0000")
    encoded = (prefix + text).encode("utf-8", errors="backslashreplace")
    if len(encoded) <= budget:
        return encoded.decode("utf-8")
    path = files.write(payload)
    suffix = f"\n[Truncated. Complete JSON agent message: {path}]"
    available = budget - len((prefix + suffix).encode("utf-8"))
    if available < 0:
        raise PairError(
            "The inbox budget cannot fit the complete agent message file reference."
        )
    preview = text.encode("utf-8", errors="backslashreplace")[
        :available
    ].decode("utf-8", errors="ignore")
    return prefix + preview + suffix
