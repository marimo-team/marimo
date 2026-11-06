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
   * The execution each submitted cell had when its run was requested.
   *
   * A cell reads as queued until the host shows a newer execution for it.
   */
  readonly submissions: ReadonlyMap<
    Protocol.CellId,
    Protocol.ExecutionId | null
  >;
  /** Cells the kernel reports as blocked by a disabled ancestor. */
  readonly blocked: ReadonlySet<Protocol.CellId>;
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
 * The execution a submission is measured against: the cell's latest on the
 * stream, or its retained result once the stream has let that execution go.
 */
export function latestExecutionId(
  inputs: Pick<CellExecutionInputs, "executions" | "results">,
  id: Protocol.CellId,
): Protocol.ExecutionId | null {
  return inputs.executions.latest.get(id) ?? inputs.results.get(id)?.id ?? null;
}

export function cellExecutionView(
  inputs: CellExecutionInputs,
  id: Protocol.CellId,
): CellExecutionView {
  const latest = latestOf(inputs.executions, id);
  const result = inputs.results.get(id) ?? null;
  const submitted =
    inputs.submissions.has(id) &&
    inputs.submissions.get(id) === latestExecutionId(inputs, id);
  let status: CellRunStatus = "idle";
  let startedAt = result === null ? null : millis(result.started_at);
  let rendered = false;
  if (latest !== null && latest.record.status !== "completed") {
    status = latest.record.status;
    startedAt = millis(latest.record.started_at) ?? startedAt;
    rendered = latest.record.outcome !== null;
  } else if (submitted) {
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

/** Cells and scratch work queued or running, plus submissions the host has not shown yet. */
export function queuedOrRunningCount(inputs: CellExecutionInputs): number {
  const pending = unfinished(inputs.executions);
  const shown = new Set(
    pending.flatMap((execution) =>
      execution.record.cell_id === null ? [] : [execution.record.cell_id],
    ),
  );
  let awaiting = 0;
  for (const [cellId, executionId] of inputs.submissions) {
    if (
      !shown.has(cellId) &&
      executionId === latestExecutionId(inputs, cellId)
    ) {
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
