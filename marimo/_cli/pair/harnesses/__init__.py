# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._cli.pair.client import PairInputError
from marimo._cli.pair.delivery import ProcessHandle
from marimo._cli.pair.harnesses.claude import ClaudeHarness
from marimo._cli.pair.harnesses.codex import CodexHarness
from marimo._cli.pair.harnesses.opencode import OpenCodeHarness

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._cli.pair.delivery import DeliveryTarget, Harness


def registered_harnesses() -> list[Harness]:
    return [CodexHarness(), ClaudeHarness(), OpenCodeHarness()]


def environment_identity(env: Mapping[str, str]) -> tuple[str, str | None]:
    found = [
        (candidate.kind, identity)
        for candidate in registered_harnesses()
        if (identity := candidate.identity(env)) is not None
    ]
    if len(found) > 1:
        raise PairInputError(
            "Nested harnesses detected. Pass --harness <kind>."
        )
    return found[0] if found else ("unknown", None)


def harness_for(kind: str) -> Harness:
    for candidate in registered_harnesses():
        if candidate.kind == kind:
            return candidate
    raise PairInputError(f"Unsupported harness: {kind}.")


def detect_target(
    env: Mapping[str, str], harness: str | None, pid: int | None = None
) -> tuple[Harness, DeliveryTarget]:
    process = None
    if pid is not None:
        import psutil

        if pid <= 0:
            raise PairInputError("--pid must be a positive process ID.")
        try:
            process = ProcessHandle.capture(pid)
            if not process.alive():
                raise PairInputError(
                    "The process selected by --pid is not running."
                )
        except psutil.Error as error:
            raise PairInputError(
                "Could not inspect the process selected by --pid."
            ) from error
    found = []
    for candidate in registered_harnesses():
        if harness is not None and candidate.kind != harness:
            continue
        target = candidate.detect(env, process=process)
        if target is not None:
            found.append((candidate, target))
    if len(found) > 1:
        raise PairInputError(
            "Nested harnesses detected. Pass --harness <kind>."
        )
    if not found:
        raise PairInputError(
            "No supported inbox detected. Run connect inside Codex, Claude Code, or OpenCode."
        )
    return found[0]
