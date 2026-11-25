/* Copyright 2026 Marimo. All rights reserved. */

/** Pure views over the replica's executions and results, by cell. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { Execution, Executions, Results } from "@/core/notebook/replica";
import { type Milliseconds, Time } from "@/utils/time";
import { completedAt, startedAt as startedAtOf } from "@/core/notebook/replica";

/** Where a cell is in its run. */
export type CellRunStatus = "idle" | "queued" | "running";

/** How a cell's last completed execution ended. */
export type CellOutcome = Protocol.ExecutionOutcome["kind"];

export interface CellExecutionView {
  readonly status: CellRunStatus;
  /** Whether a cell it depends on is disabled, so it cannot run. */
  readonly blocked: boolean;
  readonly shownBlock: "current" | "stale" | null;
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
}

/** What a cell's view is derived from. */
export interface CellExecutionInputs {
  readonly executions: Executions;
  readonly results: Results;
  /**
   * The cells of the confirmed document. A run can only reach a cell the
   * document has, and the kernel sets aside one the document has disabled.
   */
  readonly cells: ReadonlyMap<
    Protocol.CellId,
    Pick<Protocol.CellOutput, "config">
  >;
  /**
   * Cells this browser has asked to run, while the stream has not yet
   * shown the run.
   */
  readonly requested: ReadonlySet<Protocol.CellId>;
  /** Cells with a disabled ancestor in the confirmed document. */
  readonly blocked: ReadonlySet<Protocol.CellId>;
  readonly shownBlocked: ReadonlySet<Protocol.CellId>;
  /** The notebook's runtime, null while it has none or the stream is not ready. */
  readonly runtimeId: Protocol.RuntimeId | null;
}

export function outcomeOf(record: Protocol.Execution): CellOutcome | null {
  return record.state.status === "completed" ? record.state.outcome.kind : null;
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

/** Cells with a distinct disabled ancestor in the host's dependency graph. */
export function blockedDescendants(
  analysis: Protocol.AnalysisOutput,
  cells: Iterable<Protocol.CellOutput>,
): ReadonlySet<Protocol.CellId> {
  const blocked = new Set<Protocol.CellId>();
  const documentCells = [...cells];
  const roots = documentCells.filter((cell) => cell.config.disabled);
  if (roots.length === 0) {
    return blocked;
  }
  const children = new Map<Protocol.CellId, Protocol.CellId[]>(
    documentCells.map(({ id }) => [id, []]),
  );
  for (const { id } of documentCells) {
    const entry = analysis.cells[id];
    if (!entry) {
      continue;
    }
    const { parents } = entry;
    if (parents === undefined) {
      return blocked;
    }
    for (const parent of parents) {
      children.get(parent)?.push(id);
    }
  }

  // A second distinct root blocks even the first root in a cycle.
  // Beyond two roots, visiting the same subtree cannot add any blocked cells.
  const visits = new Map<Protocol.CellId, number>();
  for (const root of roots) {
    const reachable = new Set([root.id]);
    for (const id of reachable) {
      if (id !== root.id) {
        blocked.add(id);
      }
      const count = visits.get(id) ?? 0;
      if (count === 2) {
        continue;
      }
      visits.set(id, count + 1);
      for (const child of children.get(id) ?? []) {
        reachable.add(child);
      }
    }
  }
  return blocked;
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
    inputs.results.get(id)?.record.run_id;
  for (const run of inputs.executions.runs.values()) {
    if (
      run.state.status !== "completed" &&
      run.id !== planned &&
      run.origin.kind === "cells" &&
      run.origin.cell_ids.includes(id)
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
  const result = inputs.results.get(id)?.record ?? null;
  let status: CellRunStatus = "idle";
  const began = result === null ? null : startedAtOf(result);
  const ended = result === null ? null : completedAt(result);
  let startedAt = millis(began);
  if (latest !== null && latest.record.state.status !== "completed") {
    status = latest.record.state.status;
    startedAt = millis(startedAtOf(latest.record)) ?? startedAt;
  } else if (awaited(inputs, id)) {
    status = "queued";
  }
  const settled = status === "idle";
  const duration =
    settled && began !== null && ended !== null
      ? Time.parse(ended).since(Time.parse(began))
      : null;
  const blocked = inputs.blocked.has(id);
  return {
    status,
    blocked,
    shownBlock: blocked
      ? "current"
      : inputs.shownBlocked.has(id)
        ? "stale"
        : null,
    outcome: settled && result !== null ? outcomeOf(result) : null,
    live:
      result === null ||
      inputs.runtimeId === null ||
      result.runtime_id === inputs.runtimeId,
    startedAt,
    duration,
  };
}

/** Executions the host has not completed, cells and scratch alike. */
function unfinished(executions: Executions): Execution[] {
  return [...executions.executions.values()].filter(
    (execution) => execution.record.state.status !== "completed",
  );
}

export function anyRunning(executions: Executions): boolean {
  return unfinished(executions).some(
    (execution) => execution.record.state.status === "running",
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
    if (run.state.status !== "completed" && run.origin.kind === "cells") {
      for (const cellId of run.origin.cell_ids) {
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
      execution.record.state.status !== "running" ||
      execution.record.cell_id === null,
  );
}

/** Where the scratchpad's work is, from its unfinished execution if any. */
export function scratchStatus(executions: Executions): CellRunStatus {
  const scratch = unfinished(executions).find(
    (execution) => execution.record.cell_id === null,
  );
  if (scratch === undefined || scratch.record.state.status === "completed") {
    return "idle";
  }
  return scratch.record.state.status;
}

/** Cells with a running execution, in the order the host reported them. */
export function runningCellIds(executions: Executions): Protocol.CellId[] {
  return unfinished(executions).flatMap((execution) =>
    execution.record.state.status === "running" &&
    execution.record.cell_id !== null
      ? [execution.record.cell_id]
      : [],
  );
}
