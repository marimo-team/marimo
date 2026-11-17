/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";

/** An execution record paired with the local revision of its outcome. */
export interface Result {
  readonly record: Protocol.Execution;
  /** Unchanged by lifecycle-only events. */
  readonly outputVersion: number;
}

/**
 * Each document cell's last completed execution record.
 *
 * The host removes a cell's previous execution before it publishes the
 * next one. A result stays until a newer execution for the cell completes
 * or the cell leaves the document, so a cell can show its last outcome
 * while it runs again. The record and its output revision are kept; the
 * items and variables stay with the stream's copy of the execution.
 *
 * A cell has an entry from its `cell` event until its removal, null until
 * it completes once. Cells precede their executions on the stream, so a
 * completion for a cell without an entry belongs to a cell the document
 * no longer has.
 *
 * An execution the host skipped as superseded never ran, and a newer one
 * for the same cell is on its way, so it does not replace the result.
 */
export type Results = ReadonlyMap<Protocol.CellId, Result | null>;

export function retainResult(state: Results, result: Result): Results {
  const { record, outputVersion } = result;
  const cellId = record.cell_id;
  if (
    cellId === null ||
    record.status !== "completed" ||
    !state.has(cellId) ||
    (record.outcome?.kind === "skipped" &&
      record.outcome.reason === "superseded")
  ) {
    return state;
  }
  return new Map(state).set(cellId, { record, outputVersion });
}

/** Keep just the latest scratch display, independently of execution history. */
export function retainScratchResult(
  previous: Result | null,
  result: Result,
): Result | null {
  const { record, outputVersion } = result;
  if (record.cell_id !== null || record.outcome === null) {
    return previous;
  }
  const time = (execution: Protocol.Execution) =>
    Date.parse(
      execution.completed_at ?? execution.started_at ?? "1970-01-01T00:00:00Z",
    );
  if (previous !== null && time(previous.record) > time(record)) {
    return previous;
  }
  return { record, outputVersion };
}
