/* Copyright 2026 Marimo. All rights reserved. */

/** Pure views over the replica's executions and results, by cell. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { Execution, Executions, Results } from "@/core/notebook/replica";
import { type Milliseconds, Time } from "@/utils/time";

/** Where a cell is in its run. */
export type CellRunStatus = "idle" | "queued" | "running";

/** How a cell's last completed execution ended. */
export type CellOutcome = "value" | "error" | "interrupted" | "skipped";

export interface CellExecutionView {
  readonly status: CellRunStatus;
  /** Whether a cell it depends on is disabled, so it cannot run. */
  readonly blocked: boolean;
  /** Null until the cell completes once, and while it runs again. */
  readonly outcome: CellOutcome | null;
  /**
   * Whether the notebook's runtime produced the cell's result.
   *
   * A result restored from storage, or kept from a runtime that has since
   * been replaced, still shows, but nothing it bound exists in the
   * runtime. True when there is no result or no runtime to compare, as on
   * a static page.
   */
  readonly live: boolean;
  /** When the current run started, or the last one, since the epoch. */
  readonly startedAt: Milliseconds | null;
  /** How long the last completed execution took, null while the cell runs again. */
  readonly duration: Milliseconds | null;
  /** Whether the running execution has shown a value so far. TODO(MO-8404) */
  readonly rendered: boolean;
}

/** What a cell's view is derived from. */
export interface CellExecutionInputs {
  readonly executions: Executions;
  readonly results: Results;
  /**
   * The cells of the confirmed document. A run can only reach a cell the
   * document has, and the kernel sets aside one the document has disabled.
   */
  readonly cells: ReadonlyMap<Protocol.CellId, Pick<Protocol.Cell, "config">>;
  /**
   * Cells this browser has asked to run, while the stream has not yet
   * shown the run.
   */
  readonly requested: ReadonlySet<Protocol.CellId>;
  /** Cells the kernel reports as blocked by a disabled ancestor. */
  readonly blocked: ReadonlySet<Protocol.CellId>;
  /** The notebook's runtime, null while it has none or the stream is not ready. */
  readonly runtimeId: Protocol.RuntimeId | null;
}

export function outcomeOf(record: Protocol.Execution): CellOutcome | null {
  const outcome = record.outcome;
  if (outcome === null) {
    return null;
  }
  return outcome.kind;
}

function millis(iso: string | null): Milliseconds | null {
  return iso === null ? null : Time.parse(iso).toMilliseconds();
}

function latestOf(
  executions: Executions,
  id: Protocol.CellId,
): Execution | null {
  const executionId = executions.latest.get(id);
  return executionId === undefined
    ? null
    : (executions.executions.get(executionId) ?? null);
}

/**
 * Whether a run can reach `id`, meaning the document has the cell and
 * nothing keeps it from running.
 */
function runnable(inputs: CellExecutionInputs, id: Protocol.CellId): boolean {
  const cell = inputs.cells.get(id);
  return cell !== undefined && !cell.config.disabled && !inputs.blocked.has(id);
}

/**
 * Whether `id` is waiting on a run that has not planned an execution for
 * it yet.
 *
 * When the host accepts a run it names the cells that were requested, and
 * this happens before the kernel plans their executions. Until the cell's
 * execution in that run appears, the run itself is what makes the cell
 * queued. A request this browser has made works the same way until its
 * run shows up on the stream. The host keeps one execution per cell, so
 * the cell's latest execution, or its retained result once the stream has
 * let that execution go, tells which run has already planned it.
 */
function awaited(inputs: CellExecutionInputs, id: Protocol.CellId): boolean {
  if (!runnable(inputs, id)) {
    return false;
  }
  if (inputs.requested.has(id)) {
    return true;
  }
  const planned =
    latestOf(inputs.executions, id)?.record.run_id ??
    inputs.results.get(id)?.run_id;
  for (const run of inputs.executions.runs.values()) {
    if (
      run.status !== "completed" &&
      run.id !== planned &&
      run.cells.includes(id)
    ) {
      return true;
    }
  }
  return false;
}

export function cellExecutionView(
  inputs: CellExecutionInputs,
  id: Protocol.CellId,
): CellExecutionView {
  const latest = latestOf(inputs.executions, id);
  const result = inputs.results.get(id) ?? null;
  let status: CellRunStatus = "idle";
  let startedAt = result === null ? null : millis(result.started_at);
  let rendered = false;
  if (latest !== null && latest.record.status !== "completed") {
    status = latest.record.status;
    startedAt = millis(latest.record.started_at) ?? startedAt;
    rendered = latest.record.outcome !== null;
  } else if (awaited(inputs, id)) {
    status = "queued";
  }
  const settled = status === "idle";
  const duration =
    settled &&
    result !== null &&
    result.started_at !== null &&
    result.completed_at !== null
      ? Time.parse(result.completed_at).since(Time.parse(result.started_at))
      : null;
  return {
    status,
    blocked: inputs.blocked.has(id),
    outcome: settled && result !== null ? outcomeOf(result) : null,
    live:
      result === null ||
      inputs.runtimeId === null ||
      result.runtime_id === inputs.runtimeId,
    startedAt,
    duration,
    rendered,
  };
}

/** Executions the host has not completed, cells and scratch alike. */
function unfinished(executions: Executions): Execution[] {
  return [...executions.executions.values()].filter(
    (execution) => execution.record.status !== "completed",
  );
}

export function anyRunning(executions: Executions): boolean {
  return unfinished(executions).some(
    (execution) => execution.record.status === "running",
  );
}

/** Cells and scratch work queued or running, plus cells awaiting a run the kernel has not planned. */
export function queuedOrRunningCount(inputs: CellExecutionInputs): number {
  const pending = unfinished(inputs.executions);
  const shown = new Set(
    pending.flatMap((execution) =>
      execution.record.cell_id === null ? [] : [execution.record.cell_id],
    ),
  );
  const named = new Set<Protocol.CellId>(inputs.requested);
  for (const run of inputs.executions.runs.values()) {
    if (run.status !== "completed") {
      for (const cellId of run.cells) {
        named.add(cellId);
      }
    }
  }
  let awaiting = 0;
  for (const cellId of named) {
    if (!shown.has(cellId) && awaited(inputs, cellId)) {
      awaiting += 1;
    }
  }
  return pending.length + awaiting;
}

export function onlyScratchRunning(executions: Executions): boolean {
  return unfinished(executions).every(
    (execution) =>
      execution.record.status !== "running" ||
      execution.record.cell_id === null,
  );
}

/** Where the scratchpad's work is, from its unfinished execution if any. */
export function scratchStatus(executions: Executions): CellRunStatus {
  const scratch = unfinished(executions).find(
    (execution) => execution.record.cell_id === null,
  );
  if (scratch === undefined || scratch.record.status === "completed") {
    return "idle";
  }
  return scratch.record.status;
}

/** Cells with a running execution, in the order the host reported them. */
export function runningCellIds(executions: Executions): Protocol.CellId[] {
  return unfinished(executions).flatMap((execution) =>
    execution.record.status === "running" && execution.record.cell_id !== null
      ? [execution.record.cell_id]
      : [],
  );
}
