# Copyright 2026 Marimo. All rights reserved.
"""Progress events emitted by the build pipeline.

The events form a tagged union over the lifecycle of one
``build_notebook`` call. Consumers (the CLI, the editor's Build panel)
plug a callable into ``progress_callback=`` and dispatch on
:attr:`BuildProgressEvent.type`.

The shape mirrors what the editor needs to render:

- ``phase_started`` / ``phase_finished`` for an overall progress bar.
- ``cell_classified`` to tell the user which cells will run, *before*
  any expensive work.
- ``cell_executing`` / ``cell_executed`` / ``cell_failed`` per cell,
  for the running progress bar and per-cell timing.
- ``done`` (with the final :class:`BuildResult`) and ``error`` /
  ``cancelled`` as terminal states.

Events are plain frozen dataclasses (rather than TypedDicts or msgspec
Structs) so they can carry richer Python types (``Path`` etc.) and be
trivially serialized at the call site that knows the wire format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Union, cast

from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._build.build import BuildResult, CellStatus


# Sentinel default for the cell-id fields below. We type the field as
# ``CellId_t`` (a NewType over ``str``) and call sites always pass real
# ids; the empty string only exists so dataclass field ordering with
# ``init=False`` discriminator fields stays valid.
_EMPTY_CELL_ID = cast(CellId_t, "")


# The named phases of a build, in order. Matches the docstring layout
# in ``build.build_notebook``.
BuildPhase = Literal[
    "classify",
    "execute",
    "plan",
    "persist",
    "codegen",
    "gc",
]


# Static classification bucket for a single cell, surfaced to the
# editor before any cell executes so the UI can render its first set of
# badges immediately.
StaticKind = Literal["compilable", "non_compilable", "setup"]


@dataclass(frozen=True)
class PhaseStarted:
    type: Literal["phase_started"] = field(default="phase_started", init=False)
    phase: BuildPhase = "classify"


@dataclass(frozen=True)
class PhaseFinished:
    type: Literal["phase_finished"] = field(
        default="phase_finished", init=False
    )
    phase: BuildPhase = "classify"


@dataclass(frozen=True)
class CellClassified:
    type: Literal["cell_classified"] = field(
        default="cell_classified", init=False
    )
    cell_id: CellId_t = _EMPTY_CELL_ID
    name: str = ""
    display_name: str = ""
    """Human-readable label — the function name, the defs, or a snippet of
    the last expression. Falls back to ``"_"`` only when no other signal is
    available. Anonymous cells in marimo notebooks share the literal name
    ``"_"``, so the UI prefers this field."""
    static_kind: StaticKind = "compilable"


@dataclass(frozen=True)
class CellExecuting:
    type: Literal["cell_executing"] = field(
        default="cell_executing", init=False
    )
    cell_id: CellId_t = _EMPTY_CELL_ID
    name: str = ""
    display_name: str = ""


@dataclass(frozen=True)
class CellExecuted:
    type: Literal["cell_executed"] = field(default="cell_executed", init=False)
    cell_id: CellId_t = _EMPTY_CELL_ID
    name: str = ""
    display_name: str = ""
    elapsed_ms: float = 0.0


@dataclass(frozen=True)
class CellFailed:
    type: Literal["cell_failed"] = field(default="cell_failed", init=False)
    cell_id: CellId_t = _EMPTY_CELL_ID
    name: str = ""
    display_name: str = ""
    error: str = ""


@dataclass(frozen=True)
class CellPlanned:
    """A cell's final ``CellStatus`` is known.

    Emitted after the plan + persistence phases, once a cell's outcome
    is settled (``compiled`` / ``cached`` / ``elided`` / ``kept`` /
    ``setup``). The Build panel uses this to refine the live preview
    chips into ground truth.
    """

    type: Literal["cell_planned"] = field(default="cell_planned", init=False)
    cell_id: CellId_t = _EMPTY_CELL_ID
    name: str = ""
    display_name: str = ""
    status: CellStatus = "kept"


@dataclass(frozen=True)
class BuildDone:
    type: Literal["done"] = field(default="done", init=False)
    output_dir: Path | None = None
    compiled_notebook: Path | None = None
    artifacts_written: int = 0
    artifacts_cached: int = 0
    artifacts_deleted: int = 0


@dataclass(frozen=True)
class BuildError:
    type: Literal["error"] = field(default="error", init=False)
    message: str = ""
    cell_name: str | None = None


@dataclass(frozen=True)
class BuildCancelledEvent:
    type: Literal["cancelled"] = field(default="cancelled", init=False)


BuildProgressEvent = Union[
    PhaseStarted,
    PhaseFinished,
    CellClassified,
    CellExecuting,
    CellExecuted,
    CellFailed,
    CellPlanned,
    BuildDone,
    BuildError,
    BuildCancelledEvent,
]


def build_done_from_result(result: BuildResult) -> BuildDone:
    """Summarize a :class:`BuildResult` into a wire-friendly ``done`` event."""
    written = sum(1 for e in result.cell_statuses if e.status == "compiled")
    cached = sum(1 for e in result.cell_statuses if e.status == "cached")
    return BuildDone(
        output_dir=result.output_dir,
        compiled_notebook=result.compiled_notebook,
        artifacts_written=written,
        artifacts_cached=cached,
        artifacts_deleted=len(result.deleted),
    )
