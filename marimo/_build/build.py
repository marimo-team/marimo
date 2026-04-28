# Copyright 2026 Marimo. All rights reserved.
"""End-to-end orchestration for ``marimo build``.

The pipeline is:

1. :func:`~marimo._build.classify.classify_static` — partition cells
   into ``compilable`` / ``non_compilable`` from the AST.
2. :class:`~marimo._build.runner.BuildRunner` — execute every
   compilable cell, capturing its defs.
3. :func:`~marimo._build.plan.compute_plan` — turn the post-execution
   facts into a :class:`~marimo._build.plan.CellKind` per cell.
4. Persist artifacts for every ``LOADER`` cell, content-addressed by
   :func:`~marimo._build.hash.compilable_hash`.
5. :func:`~marimo._build.codegen.emit_compiled_notebook` — render the
   compiled ``.py`` file.
6. Garbage-collect stale artifacts left over from previous runs.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from marimo import _loggers
from marimo._ast.app import InternalApp
from marimo._ast.load import load_app
from marimo._build.classify import classify_static
from marimo._build.codegen import CellArtifact, emit_compiled_notebook
from marimo._build.events import (
    BuildCancelledEvent,
    BuildError,
    CellClassified,
    CellPlanned,
    PhaseFinished,
    PhaseStarted,
    build_done_from_result,
)
from marimo._build.hash import compilable_hash, short_hash
from marimo._build.plan import CellKind, compute_plan
from marimo._build.runner import BuildCancelled, BuildRunner
from marimo._build.serialize import write_artifact
from marimo._version import __version__

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._ast.cell import CellImpl
    from marimo._build.events import BuildProgressEvent
    from marimo._types.ids import CellId_t


LOGGER = _loggers.marimo_logger()


# Files of these names live alongside the compiled notebook and are
# preserved by stale-artifact GC.
MANIFEST_FILENAME = ".manifest.json"
DEFAULT_BUILD_ROOT = "__marimo_build__"


# Status of an individual cell at the end of a build.
CellStatus = Literal[
    "compiled",  # LOADER: artifact written this run
    "cached",  # LOADER: artifact existed on disk; reused
    "elided",  # ELIDED
    "kept",  # VERBATIM
    "setup",  # SETUP
]


@dataclass(frozen=True)
class CellStatusEntry:
    """One cell's outcome in the build, in source order.

    The list-of-records shape (rather than a name-keyed dict)
    preserves every cell — anonymous ``_``-named cells, which can
    appear many times in a single notebook, are counted distinctly.
    """

    cell_id: CellId_t
    name: str
    """The function name as written in the source. ``"_"`` for anonymous cells."""
    display_name: str
    """Best-effort human-readable label.

    Falls back to the cell's defs or its last expression when ``name``
    is ``"_"``, since lining up ten ``_``s in CLI output is uniquely
    unhelpful.
    """
    status: CellStatus


@dataclass
class BuildResult:
    """Summary of one ``build_notebook`` invocation."""

    output_dir: Path
    compiled_notebook: Path
    artifacts: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)
    cell_statuses: list[CellStatusEntry] = field(default_factory=list)

    def status_for(self, name: str) -> CellStatus:
        """Status of the unique cell named ``name``.

        Convenience for tests and tooling on notebooks where every
        cell has a distinct (named) function. Raises
        :py:class:`LookupError` if the name doesn't appear or appears
        more than once.
        """
        matches = [e.status for e in self.cell_statuses if e.name == name]
        if len(matches) != 1:
            raise LookupError(
                f"expected exactly one cell named {name!r}, found {len(matches)}"
            )
        return matches[0]


def build_notebook(
    notebook_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    force: bool = False,
    progress_callback: Callable[[BuildProgressEvent], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> BuildResult:
    """Pre-execute the input-free DAG slice and emit a compiled notebook.

    Parameters
    ----------
    notebook_path:
        Path to the source ``.py`` notebook.
    output_dir:
        Where artifacts and the compiled notebook are written. Defaults
        to ``<notebook_dir>/__marimo_build__/<stem>/``.
    force:
        Recompute every artifact, even if its content-addressed file
        already exists on disk.
    progress_callback:
        Optional sink for :class:`BuildProgressEvent`s emitted as the
        pipeline advances. The CLI ignores it; the editor's Build panel
        forwards events to the frontend over the websocket.
    should_cancel:
        Optional poll fn checked between cells in the runner. Returning
        True raises :class:`BuildCancelled`, which this function
        re-raises after emitting a ``cancelled`` progress event.
    """
    notebook_path = Path(notebook_path).resolve()
    if not notebook_path.exists():
        raise FileNotFoundError(notebook_path)

    if output_dir is None:
        output_dir = (
            notebook_path.parent / DEFAULT_BUILD_ROOT / notebook_path.stem
        )
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    def _emit(event: BuildProgressEvent) -> None:
        if progress_callback is not None:
            progress_callback(event)

    try:
        return _build_notebook_inner(
            notebook_path=notebook_path,
            output_dir=output_dir,
            force=force,
            emit=_emit,
            progress_callback=progress_callback,
            should_cancel=should_cancel,
        )
    except BuildCancelled:
        _emit(BuildCancelledEvent())
        raise
    except Exception as e:
        # Best-effort tail event so the UI can show a terminal error
        # state. The CLI rewraps these in click.ClickException; the
        # exception still propagates.
        _emit(BuildError(message=str(e)))
        raise


def _build_notebook_inner(
    *,
    notebook_path: Path,
    output_dir: Path,
    force: bool,
    emit: Callable[[BuildProgressEvent], None],
    progress_callback: Callable[[BuildProgressEvent], None] | None,
    should_cancel: Callable[[], bool] | None,
) -> BuildResult:
    app = load_app(notebook_path)
    if app is None:
        raise RuntimeError(
            f"Notebook {notebook_path} could not be loaded; "
            "is it empty or invalid?"
        )

    internal = InternalApp(app)
    from marimo._build.events import StaticKind

    emit(PhaseStarted(phase="classify"))
    classification = classify_static(internal.graph, internal.cell_manager)
    setup_id = internal.cell_manager.setup_cell_id
    for cid, cell in internal.graph.cells.items():
        name = internal.cell_manager.cell_name(cid)
        static_kind: StaticKind
        if cid == setup_id:
            static_kind = "setup"
        elif cid in classification.compilable:
            static_kind = "compilable"
        else:
            static_kind = "non_compilable"
        emit(
            CellClassified(
                cell_id=cid,
                name=name,
                display_name=display_name(name, cell),
                static_kind=static_kind,
            )
        )
    emit(PhaseFinished(phase="classify"))

    emit(PhaseStarted(phase="execute"))
    runner = BuildRunner(
        internal,
        classification,
        progress_callback=progress_callback,
        should_cancel=should_cancel,
    )
    runner.run()
    emit(PhaseFinished(phase="execute"))

    emit(PhaseStarted(phase="plan"))
    plan = compute_plan(
        graph=internal.graph,
        cell_manager=internal.cell_manager,
        classification=classification,
        captured_defs=runner.captured_defs,
    )
    emit(PhaseFinished(phase="plan"))

    emit(PhaseStarted(phase="persist"))
    # Hashes are computed against the *statically* compilable subgraph,
    # because parents that aren't compilable have their data inlined
    # into the cell's source at build time and therefore don't
    # contribute identity to the artifact.
    hash_cache: dict[CellId_t, bytes] = {}
    artifacts_by_cell: dict[CellId_t, list[CellArtifact]] = {}
    artifact_index: dict[str, dict[str, str]] = {}
    written: set[Path] = set()
    loader_statuses: dict[CellId_t, CellStatus] = {}

    for cell_id, cell_plan in plan.cells.items():
        if cell_plan.kind is not CellKind.LOADER:
            continue
        digest = compilable_hash(
            cell_id,
            graph=internal.graph,
            compilable=classification.compilable,
            cache=hash_cache,
        )
        h = short_hash(digest)

        defs = runner.captured_defs[cell_id]
        cell_artifacts: list[CellArtifact] = []
        was_cached = True
        for def_name, kind in cell_plan.loader_defs:
            ext = "parquet" if kind == "dataframe" else "json"
            filename = f"{def_name}-{h}.{ext}"
            path = output_dir / filename
            cell_artifacts.append(
                CellArtifact(def_name=def_name, filename=filename, kind=kind)
            )
            artifact_index[def_name] = {"file": filename, "kind": kind}
            written.add(path)
            if force or not path.exists():
                write_artifact(defs[def_name], path, kind)
                was_cached = False

        artifacts_by_cell[cell_id] = cell_artifacts
        loader_statuses[cell_id] = "cached" if was_cached else "compiled"
    emit(PhaseFinished(phase="persist"))

    emit(PhaseStarted(phase="codegen"))
    source = emit_compiled_notebook(
        app=internal,
        plan=plan,
        artifacts=artifacts_by_cell,
        config=app._config,
    )
    compiled_path = output_dir / notebook_path.name
    compiled_path.write_text(source, encoding="utf-8")
    emit(PhaseFinished(phase="codegen"))

    # Build the per-cell status list in source order. Loaders pull
    # from loader_statuses (compiled vs cached); everything else maps
    # directly from its CellKind.
    cell_statuses: list[CellStatusEntry] = []
    for cell_id, cell_plan in plan.cells.items():
        status = loader_statuses.get(cell_id) or _status_for(cell_plan.kind)
        name = internal.cell_manager.cell_name(cell_id)
        # ``plan.cells`` is built from ``internal.graph.cells`` so this
        # lookup always succeeds; the .get() spelling is purely for
        # mypy's benefit since ``cell`` was rebound earlier in this
        # function and we can't shadow the narrower type.
        label = display_name(name, internal.graph.cells.get(cell_id))
        cell_statuses.append(
            CellStatusEntry(
                cell_id=cell_id,
                name=name,
                display_name=label,
                status=status,
            )
        )
        emit(
            CellPlanned(
                cell_id=cell_id,
                name=name,
                display_name=label,
                status=status,
            )
        )

    # Write the manifest before GC so a partial GC failure can't lose
    # data — the manifest lists everything we want to keep.
    #
    # ``artifacts`` is a {def_name: {file, kind}} mapping rather than a
    # plain list so downstream tools can look up "where is the
    # ``customers`` table?" by name without parsing filenames or
    # extensions.
    manifest = {
        "version": __version__,
        "compiled": compiled_path.name,
        "artifacts": dict(sorted(artifact_index.items())),
    }
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    emit(PhaseStarted(phase="gc"))
    deleted = _gc_stale(output_dir, written, compiled_path)
    emit(PhaseFinished(phase="gc"))

    result = BuildResult(
        output_dir=output_dir,
        compiled_notebook=compiled_path,
        artifacts=sorted(written),
        deleted=deleted,
        cell_statuses=cell_statuses,
    )
    emit(build_done_from_result(result))
    return result


def _status_for(kind: CellKind) -> CellStatus:
    if kind is CellKind.SETUP:
        return "setup"
    if kind is CellKind.ELIDED:
        return "elided"
    if kind is CellKind.VERBATIM:
        return "kept"
    # LOADER cases are handled by the artifact-writing loop, which
    # records "compiled" or "cached" before this fallback runs.
    raise AssertionError(
        f"unreachable: LOADER status not pre-recorded ({kind})"
    )


# Maximum length of a derived display name before it gets truncated
# with an ellipsis. Picked so the CLI's status line stays under 80
# columns even with long status prefixes.
_DISPLAY_NAME_MAX = 40


def display_name(name: str, cell: CellImpl | None) -> str:
    """Best-effort human label for a cell.

    Order of preference:

    1. The function name, if the user gave the cell one (anything
       other than ``"_"``).
    2. The cell's defs joined together — "this cell produces X" is
       what the user almost always wants to know.
    3. The cell's last expression or assignment target, which catches
       the ``_chart`` / ``mo.ui.table(...)`` "display-only" pattern.
    4. ``"_"`` as a final fallback for cells we genuinely can't
       summarize.
    """
    if name and name != "_":
        return name
    if cell is None:
        return name or "_"
    if cell.defs:
        return ", ".join(sorted(cell.defs))
    return _last_statement_label(cell.mod) or "_"


# Backwards-compatible alias for the underscore-prefixed spelling that
# was used internally before this helper had any external callers.
_display_name = display_name


def _last_statement_label(mod: ast.Module) -> str | None:
    """Compact label from the last meaningful statement of a cell body.

    Skips trailing ``return`` statements inserted by marimo's codegen
    so the derived label reflects what the user actually wrote.
    """
    for node in reversed(mod.body):
        if isinstance(node, ast.Return):
            continue
        if isinstance(node, ast.Expr):
            return _truncate(ast.unparse(node.value))
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                return target.id
        return _truncate(ast.unparse(node))
    return None


def _truncate(text: str, max_len: int = _DISPLAY_NAME_MAX) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _gc_stale(
    output_dir: Path,
    written: set[Path],
    compiled_path: Path,
) -> list[Path]:
    """Delete top-level ``*.parquet``/``*.json`` files not in the manifest.

    Conservative: only files matching the artifact suffix at the top
    level are eligible. Subdirectories, the manifest, and the compiled
    notebook are always preserved. This avoids clobbering files a user
    happened to drop in the build dir.
    """
    expected = {p.name for p in written}
    expected.add(MANIFEST_FILENAME)
    expected.add(compiled_path.name)
    deleted: list[Path] = []
    for child in output_dir.iterdir():
        if not child.is_file() or child.name in expected:
            continue
        if child.suffix not in {".parquet", ".json"}:
            continue
        try:
            child.unlink()
            deleted.append(child)
        except OSError as e:  # pragma: no cover - filesystem edge case
            LOGGER.warning("Could not delete stale artifact %s: %s", child, e)
    return deleted
