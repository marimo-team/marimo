/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { NotebookResource } from "@marimo-team/client";

/**
 * Each document cell's last completed execution record.
 *
 * The host removes a cell's previous execution before it publishes the
 * next one. A result stays until a newer execution for the cell completes
 * or the cell leaves the document, so a cell can show its last outcome
 * while it runs again. Only the record is kept. Its outcome carries the
 * cell's output, while items and variables stay with the stream's copy of
 * the execution.
 *
 * A cell has an entry from its `cell` event until its removal, null until
 * it completes once. Cells precede their executions on the stream, so a
 * completion for a cell without an entry belongs to a cell the document
 * no longer has.
 *
 * An execution the host skipped as superseded never ran, and a newer one
 * for the same cell is on its way, so it does not replace the result.
 */
export type Results = ReadonlyMap<Protocol.CellId, Protocol.Execution | null>;

export const results: NotebookResource<Results, "cell" | "execution"> = {
  initial: new Map(),
  on: {
    cell: (state, { data }) =>
      state.has(data.cell.id) ? state : new Map(state).set(data.cell.id, null),
    "cell.removed": (state, { data }) => {
      if (!state.has(data.id)) {
        return state;
      }
      const next = new Map(state);
      next.delete(data.id);
      return next;
    },
    execution: (state, { data: { execution } }) => {
      const cellId = execution.cell_id;
      if (
        cellId === null ||
        execution.status !== "completed" ||
        !state.has(cellId) ||
        (execution.outcome?.kind === "skipped" &&
          execution.outcome.reason === "superseded")
      ) {
        return state;
      }
      return new Map(state).set(cellId, execution);
    },
  },
};
