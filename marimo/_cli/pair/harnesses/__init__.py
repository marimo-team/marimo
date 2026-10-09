# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._cli.pair.client import PairInputError
from marimo._cli.pair.harnesses.codex import CodexAdapter

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._cli.pair.delivery import DeliveryTarget, HarnessAdapter


def adapters() -> list[HarnessAdapter]:
    return [CodexAdapter()]


def environment_identity(env: Mapping[str, str]) -> tuple[str, str | None]:
    found = [
        (adapter.kind, identity)
        for adapter in adapters()
        if (identity := adapter.identity(env)) is not None
    ]
    if len(found) > 1:
        raise PairInputError(
            "Nested harnesses detected. Pass --harness <kind>."
        )
    return found[0] if found else ("unknown", None)


def adapter_for(kind: str) -> HarnessAdapter:
    for adapter in adapters():
        if adapter.kind == kind:
            return adapter
    raise PairInputError(f"Unsupported harness: {kind}.")


def detect_target(
    env: Mapping[str, str], harness: str | None
) -> tuple[HarnessAdapter, DeliveryTarget]:
    found = []
    for adapter in adapters():
        if harness is not None and adapter.kind != harness:
            continue
        target = adapter.detect(env)
        if target is not None:
            found.append((adapter, target))
    if len(found) > 1:
        raise PairInputError(
            "Nested harnesses detected. Pass --harness <kind>."
        )
    if not found:
        raise PairInputError(
            "No supported inbox detected. Run connect inside Codex."
        )
    return found[0]
