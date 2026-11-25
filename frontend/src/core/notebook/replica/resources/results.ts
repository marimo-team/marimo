/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { completedAt, shown, startedAt } from "../execution-state";

/** An execution record and its output, with the local revision of what it shows. */
export interface Result {
  readonly record: Protocol.ExecutionOutput;
  /** The execution's output item, null until it sets one. */
  readonly output: Protocol.Output | null;
  /** Unchanged by lifecycle-only events. */
  readonly outputVersion: number;
}

/**
 * Each document cell's last completed execution record.
 *
 * The host removes a cell's previous execution before it publishes the
 * next one. A result stays until a newer execution for the cell completes
 * or the cell leaves the document, so a cell can show its last outcome
 * while it runs again. The record, its output, and the output revision are
 * kept; the items and variables stay with the stream's copy of the execution.
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
  const { record, output, outputVersion } = result;
  const cellId = record.cell_id;
  if (
    cellId === null ||
    record.state.status !== "completed" ||
    !state.has(cellId) ||
    (record.state.outcome.kind === "skipped" &&
      record.state.outcome.reason === "superseded")
  ) {
    return state;
  }
  return new Map(state).set(cellId, { record, output, outputVersion });
}

/** Keep just the latest scratch display, independently of execution history. */
export function retainScratchResult(
  previous: Result | null,
  result: Result,
): Result | null {
  const { record, output, outputVersion } = result;
  if (record.cell_id !== null || shown(result) === null) {
    return previous;
  }
  const time = (execution: Protocol.ExecutionOutput) =>
    Date.parse(
      completedAt(execution) ?? startedAt(execution) ?? "1970-01-01T00:00:00Z",
    );
  if (previous !== null && time(previous.record) > time(record)) {
    return previous;
  }
  return { record, output, outputVersion };
}
