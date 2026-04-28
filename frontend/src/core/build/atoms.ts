/* Copyright 2026 Marimo. All rights reserved. */

/**
 * State for the in-editor Build panel.
 *
 * Two atoms:
 *
 * - {@link buildPreviewAtom} — per-cell prediction of the compiled-notebook
 *   outcome, refreshed by hitting `POST /api/build/preview`. Drives the
 *   live cell badges before any build has run.
 * - {@link buildStateAtom} — current build status (idle / running / done /
 *   error / cancelled), progress counters, last build's per-cell outcomes,
 *   and the result summary. Driven by the `build-event` WebSocket op.
 *
 * The cell badges shown in the editor prefer the build-state map (ground
 * truth from a real build) over the preview map (best-effort prediction).
 */

import { atom } from "jotai";
import type { CellId } from "@/core/cells/ids";
import type { BuildEventNotification } from "@/core/network/types";
import { Logger } from "@/utils/Logger";

export type BuildStatus =
  | "idle"
  | "running"
  | "success"
  | "error"
  | "cancelled";

/** A cell's predicted outcome in the compiled notebook. */
export interface BuildPreviewCell {
  cellId: CellId;
  name: string;
  /**
   * Human-readable label — falls back to the cell's defs or last
   * expression when {@link name} is the anonymous `_`. The Build panel
   * prefers this for display.
   */
  displayName: string;
  /** "loader" | "elided" | "verbatim" | "setup" | null */
  predictedKind: string | null;
  /**
   * "predicted" | "stale" | "unmaterialized" | "static" |
   * "non_compilable" | "setup"
   */
  confidence: string;
}

/**
 * One cell's status while the build is running, then once it's done.
 *
 * `executing` and `executed` mirror the runner's progress events;
 * `final` is the post-plan status (compiled / cached / elided / kept /
 * setup), populated by `cell_planned` events.
 */
export interface BuildCellStatus {
  cellId: CellId;
  name: string;
  /** Human-readable label, see {@link BuildPreviewCell.displayName}. */
  displayName: string;
  state: "idle" | "executing" | "executed" | "failed";
  elapsedMs?: number;
  error?: string;
  /** "compiled" | "cached" | "elided" | "kept" | "setup" */
  final?: string;
}

export interface BuildResultSummary {
  outputDir?: string;
  compiledNotebook?: string;
  artifactsWritten: number;
  artifactsCached: number;
  artifactsDeleted: number;
}

export interface BuildState {
  buildId?: string;
  status: BuildStatus;
  /** Phases in flight; key is the phase name. */
  activePhase?: string;
  /** Number of compilable cells classified at the start of the build. */
  totalCompilable: number;
  /** Number of compilable cells whose `cell_executed` we've seen. */
  executedCount: number;
  /** Cell currently in `cell_executing`, for the progress label. */
  currentCellName?: string;
  cellResults: Map<CellId, BuildCellStatus>;
  result?: BuildResultSummary;
  error?: { message: string; cellName?: string | null };
}

const INITIAL_STATE: BuildState = {
  status: "idle",
  totalCompilable: 0,
  executedCount: 0,
  cellResults: new Map(),
};

/** Per-cell predictions from `POST /api/build/preview`. */
export const buildPreviewAtom = atom<Map<CellId, BuildPreviewCell>>(new Map());

/** Current build state, populated by `build-event` WebSocket ops. */
export const buildStateAtom = atom<BuildState>(INITIAL_STATE);

/**
 * Apply one `BuildEventNotification` to the in-flight build state.
 *
 * Stale events (a different `build_id`) are ignored — this happens after
 * a cancel-and-restart or when the user reconnects mid-build.
 */
export function applyBuildEvent(
  state: BuildState,
  event: BuildEventNotification,
): BuildState {
  const payload = event.payload as Record<string, unknown>;

  // `classify` is the first phase emitted by every build, so we use it
  // as the build-boundary marker: any prior state for this or another
  // build is torn down. Outside of that one event, anything carrying a
  // foreign build_id is a late straggler from a cancelled build and
  // gets dropped.
  const isClassifyStart =
    event.event_type === "phase_started" && payload.phase === "classify";
  if (
    !isClassifyStart &&
    state.buildId !== undefined &&
    event.build_id !== state.buildId
  ) {
    return state;
  }

  switch (event.event_type) {
    case "phase_started": {
      const phase = String(payload.phase ?? "");
      if (isClassifyStart) {
        return {
          ...INITIAL_STATE,
          buildId: event.build_id,
          status: "running",
          activePhase: phase,
        };
      }
      return { ...state, activePhase: phase };
    }
    case "phase_finished":
      return { ...state, activePhase: undefined };
    case "cell_classified": {
      const staticKind = String(payload.static_kind ?? "");
      if (staticKind !== "compilable") {
        return state;
      }
      return { ...state, totalCompilable: state.totalCompilable + 1 };
    }
    case "cell_executing": {
      const cellId = payload.cell_id as CellId;
      const name = String(payload.name ?? "");
      const displayName = String(payload.display_name ?? name);
      const next = new Map(state.cellResults);
      next.set(cellId, {
        cellId,
        name,
        displayName,
        state: "executing",
      });
      return {
        ...state,
        cellResults: next,
        currentCellName: displayName,
      };
    }
    case "cell_executed": {
      const cellId = payload.cell_id as CellId;
      const name = String(payload.name ?? "");
      const displayName = String(payload.display_name ?? name);
      const elapsedMs = Number(payload.elapsed_ms ?? 0);
      const next = new Map(state.cellResults);
      const existing = next.get(cellId);
      next.set(cellId, {
        ...existing,
        cellId,
        name,
        displayName,
        state: "executed",
        elapsedMs,
      });
      return {
        ...state,
        cellResults: next,
        executedCount: state.executedCount + 1,
        currentCellName: undefined,
      };
    }
    case "cell_failed": {
      const cellId = payload.cell_id as CellId;
      const name = String(payload.name ?? "");
      const displayName = String(payload.display_name ?? name);
      const error = String(payload.error ?? "");
      const next = new Map(state.cellResults);
      const existing = next.get(cellId);
      next.set(cellId, {
        ...existing,
        cellId,
        name,
        displayName,
        state: "failed",
        error,
      });
      return { ...state, cellResults: next };
    }
    case "cell_planned": {
      const cellId = payload.cell_id as CellId;
      const name = String(payload.name ?? "");
      const displayName = String(payload.display_name ?? name);
      const final = String(payload.status ?? "");
      const next = new Map(state.cellResults);
      const existing = next.get(cellId);
      next.set(cellId, {
        cellId,
        name,
        displayName,
        state: existing?.state ?? "executed",
        elapsedMs: existing?.elapsedMs,
        final,
      });
      return { ...state, cellResults: next };
    }
    case "done": {
      return {
        ...state,
        status: "success",
        activePhase: undefined,
        result: {
          outputDir: payload.output_dir as string | undefined,
          compiledNotebook: payload.compiled_notebook as string | undefined,
          artifactsWritten: Number(payload.artifacts_written ?? 0),
          artifactsCached: Number(payload.artifacts_cached ?? 0),
          artifactsDeleted: Number(payload.artifacts_deleted ?? 0),
        },
      };
    }
    case "error": {
      return {
        ...state,
        status: "error",
        activePhase: undefined,
        error: {
          message: String(payload.message ?? "Build failed"),
          cellName: (payload.cell_name as string | null | undefined) ?? null,
        },
      };
    }
    case "cancelled":
      return { ...state, status: "cancelled", activePhase: undefined };
    default:
      Logger.warn("Unknown build event", event);
      return state;
  }
}
