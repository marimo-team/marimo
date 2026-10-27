/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { NotebookResource } from "@marimo-team/client";

/**
 * The notebook's content at one revision.
 *
 * The revision record carries the cell order, app config, etags, and
 * version. Each cell in its order has a record in `cells`.
 */
export interface Document {
  readonly revision: Protocol.Document;
  readonly cells: ReadonlyMap<Protocol.CellId, Protocol.Cell>;
}

/** The records of a revision still being received. */
interface PendingDocument {
  /** Null until the `document` event that closes the group arrives. */
  readonly revision: Protocol.Document | null;
  readonly cells: ReadonlyMap<Protocol.CellId, Protocol.Cell>;
}

/**
 * The confirmed document and the revision being assembled after it.
 *
 * A snapshot's records are pending until `ready`. A live revision is pending
 * from its first cell until its `document` event.
 */
interface DocumentState {
  readonly current: Document | null;
  readonly pending: PendingDocument | null;
}

function pendingOf(state: DocumentState): PendingDocument {
  return (
    state.pending ?? {
      revision: state.current?.revision ?? null,
      cells: state.current?.cells ?? new Map(),
    }
  );
}

/** Confirm a revision whose records are complete. */
function publish(
  revision: Protocol.Document,
  cells: ReadonlyMap<Protocol.CellId, Protocol.Cell>,
): DocumentState {
  const order = new Set(revision.order);
  if (
    order.size !== revision.order.length ||
    order.size !== cells.size ||
    [...order].some((id) => !cells.has(id)) ||
    [...cells.values()].some((cell) => cell.version > revision.version)
  ) {
    throw new Error("Document records do not match its revision and order");
  }
  return { current: { revision, cells }, pending: null };
}

export const document: NotebookResource<DocumentState, "cell" | "document"> = {
  initial: { current: null, pending: null },
  on: {
    cell: (state, { data }) => {
      const pending = pendingOf(state);
      return {
        ...state,
        pending: {
          revision: pending.revision,
          cells: new Map(pending.cells).set(data.cell.id, data.cell),
        },
      };
    },
    "cell.removed": (state, { data }) => {
      const pending = pendingOf(state);
      if (!pending.cells.has(data.id)) {
        return state;
      }
      const cells = new Map(pending.cells);
      cells.delete(data.id);
      return { ...state, pending: { ...pending, cells } };
    },
    document: (state, { data }, { phase }) => {
      const { cells } = pendingOf(state);
      return phase === "snapshot"
        ? { ...state, pending: { revision: data.document, cells } }
        : publish(data.document, cells);
    },
    ready: (state, _event, { phase }) => {
      if (state.pending === null) {
        return state;
      }
      if (phase === "live") {
        throw new Error("Stream ended with an incomplete document update");
      }
      return state.pending.revision === null
        ? { current: null, pending: null }
        : publish(state.pending.revision, state.pending.cells);
    },
  },
};
