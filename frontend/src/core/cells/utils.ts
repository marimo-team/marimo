/* Copyright 2026 Marimo. All rights reserved. */

import {
  type CellError,
  type CellExecutionInputs,
  type CellExecutionView,
  type CellFreshness,
  type CellFreshnessLookup,
  type CellOutput,
  cellExecutionView,
} from "@/core/executions";
import type { Executions } from "@/core/notebook/replica";
import { isErrorMime } from "../mime";
import type { NotebookState } from "./cells";
import type { CellId } from "./ids";
import type { CellData } from "./types";

export function notebookCells(state: NotebookState) {
  return state.cellIds.map((cellId) => state.cellData[cellId]);
}

export function disabledCellIds(state: NotebookState) {
  const { cellIds, cellData } = state;
  const disabledCells: CellId[] = [];
  for (const cellId of cellIds) {
    const cell = cellData[cellId];
    if (cell.config.disabled) {
      disabledCells.push(cellId);
    }
  }
  return disabledCells;
}

export function enabledCellIds(state: NotebookState) {
  const { cellIds, cellData } = state;
  const enabledCells: CellId[] = [];
  for (const cellId of cellIds) {
    const cell = cellData[cellId];
    if (!cell.config.disabled) {
      enabledCells.push(cellId);
    }
  }
  return enabledCells;
}

export function canUndoDeletes(state: NotebookState) {
  return state.history.length > 0;
}

/**
 * Label for the undo action based on the last history entry type.
 */
export function getUndoLabel(state: NotebookState): string {
  const last = state.history[state.history.length - 1];
  if (!last) {
    return "Undo cell deletion";
  }
  return last.type === "move" ? "Undo move" : "Undo cell deletion";
}

/**
 * Summarize the run state of the given descendants, whether any is stale,
 * errored, or running.
 */
export function getDescendantsStatus(
  executions: CellExecutionInputs,
  freshness: CellFreshnessLookup,
  descendants: readonly CellId[],
) {
  const views = descendants.map((id) => cellExecutionView(executions, id));
  const stale = descendants.some(
    (id) => freshness(id).sourceChanged || freshness(id).inputsChanged,
  );
  const errored = views.some((view) => view.outcome === "failed");
  const runningOrQueued = views.some(
    (view) => view.status === "running" || view.status === "queued",
  );

  return {
    stale,
    errored,
    runningOrQueued,
  };
}

type RunReason = "not-run" | "source" | "inputs" | "interrupted";

export function cellRunReason(
  execution: Pick<CellExecutionView, "status" | "live" | "outcome" | "blocked">,
  freshness: CellFreshness,
  cell: Pick<CellData, "code" | "config">,
): RunReason | null {
  if (execution.status !== "idle") {
    return null;
  }
  if (isUninstantiated(execution) && cell.code.trim()) {
    return "not-run";
  }
  if (freshness.sourceChanged) {
    return "source";
  }
  if (execution.outcome === "cancelled") {
    return "interrupted";
  }
  return freshness.inputsChanged && !cell.config.disabled && !execution.blocked
    ? "inputs"
    : null;
}

function* cellsNeedingRun(
  state: NotebookState,
  executions: CellExecutionInputs,
  freshness: CellFreshnessLookup,
): Generator<[CellId, RunReason]> {
  for (const id of state.cellIds) {
    const view = cellExecutionView(executions, id);
    const changes = freshness(id);
    const reason = cellRunReason(view, changes, state.cellData[id]);
    if (reason !== null) {
      yield [id, reason];
    } else if (changes.sourceChanged && inFlight(executions.executions, id)) {
      // The run action can submit an edit made after the host planned this cell.
      yield [id, "source"];
    }
  }
}

export function staleCellIds(
  state: NotebookState,
  executions: CellExecutionInputs,
  freshness: CellFreshnessLookup,
) {
  return Array.from(
    cellsNeedingRun(state, executions, freshness),
    ([id]) => id,
  );
}

export function notebookRunReason(
  state: NotebookState,
  executions: CellExecutionInputs,
  freshness: CellFreshnessLookup,
): RunReason | null {
  let reason: RunReason | null = null;
  for (const [, pending] of cellsNeedingRun(state, executions, freshness)) {
    if (pending !== "inputs") {
      return pending;
    }
    reason = pending;
  }
  return reason;
}

/** Whether the host holds a planned or started execution of the cell that has not completed. */
function inFlight(executions: Executions, cellId: CellId): boolean {
  const latest = executions.latest.get(cellId);
  const record =
    latest === undefined
      ? undefined
      : executions.executions.get(latest)?.record;
  return record !== undefined && record.state.status !== "completed";
}

/**
 * Whether a cell has not run in the notebook's runtime: it has no result,
 * or only one that another runtime produced, and nothing is in flight.
 */
export function isUninstantiated({
  status,
  outcome,
  live,
}: Pick<CellExecutionView, "status" | "outcome" | "live">) {
  return (
    (outcome === null || !live) && status !== "queued" && status !== "running"
  );
}

export function cellStatusClasses({
  needsRun,
  errored,
  stopped,
  disabled,
  blocked,
}: {
  needsRun: boolean;
  errored: boolean;
  stopped: boolean;
  disabled: boolean | undefined;
  blocked: boolean;
}) {
  return {
    "needs-run": needsRun,
    "has-error": errored,
    stopped,
    disabled: disabled ?? false,
    stale: blocked,
  };
}

/**
 * Status classes for a published cell (read or present mode, output only).
 */
export function publishedCellClasses({
  errored,
  stopped,
}: {
  errored: boolean;
  stopped: boolean;
}) {
  return {
    published: true,
    "has-error": errored,
    stopped: stopped,
  };
}

/**
 * Whether a published cell (read or present mode) should be hidden.
 *
 * Errored, interrupted, and stopped cells (and error outputs) are hidden in
 * published views, unless `show_tracebacks` is enabled and the output carries
 * an exception traceback to display inline.
 */
export function shouldHidePublishedCell({
  errored,
  interrupted,
  stopped,
  output,
  showErrorTracebacks,
}: {
  errored: boolean;
  interrupted: boolean;
  stopped: boolean;
  output: CellOutput | null;
  showErrorTracebacks: boolean;
}): boolean {
  const outputIsError = isErrorMime(output?.mimetype);
  const hasTraceback =
    showErrorTracebacks &&
    outputIsError &&
    Array.isArray(output?.data) &&
    output.data.some(
      (e: CellError) =>
        e.type === "exception" && "traceback" in e && e.traceback,
    );
  return (errored || interrupted || stopped || outputIsError) && !hasTraceback;
}
