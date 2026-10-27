/* Copyright 2026 Marimo. All rights reserved. */

/** A backend that serves a document snapshot without a host. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { NotebookBackend } from "./backend";

/** A document snapshot with its own identity and revision metadata. */
export interface StaticNotebookSnapshot {
  readonly notebook: Omit<Protocol.Notebook, "operations">;
  readonly document: Protocol.Document;
  readonly cells: readonly Protocol.Cell[];
}

/**
 * Serve a document without a server, runtime, or mutation operations.
 * Callers and readers must treat the snapshot records as immutable.
 */
export function createStaticNotebookBackend(
  snapshot: StaticNotebookSnapshot,
): NotebookBackend {
  const frames: Protocol.Event[] = [
    {
      event: "notebook",
      data: { notebook: { ...snapshot.notebook, operations: [] } },
    },
    ...snapshot.cells.map((cell): Protocol.CellEvent => ({
      event: "cell",
      data: { cell },
    })),
    { event: "document", data: { document: snapshot.document } },
    { event: "ready", id: "static", data: {} },
  ];

  return {
    transport: ({ cursor, signal }, { open, message }) =>
      new Promise((resolve) => {
        if (signal.aborted) {
          resolve();
          return;
        }
        // Finishing would ask NotebookEvents to reconnect. A snapshot stays open
        // until its reader closes, even though there are no more updates.
        signal.addEventListener("abort", () => resolve(), { once: true });
        open();
        if (cursor !== null && !signal.aborted) {
          message({ event: "reset", data: {} });
        }
        for (const frame of frames) {
          if (signal.aborted) {
            return;
          }
          message(frame);
        }
      }),
    notebook: () => ({
      edit: async (_changes, options) => {
        options?.signal?.throwIfAborted();
        return {
          ok: false,
          status: 501,
          problem: {
            type: "tag:marimo.io,2026:host/unsupported-operation",
            title: "Unsupported operation",
            status: 501,
            detail: "Static notebooks do not support editing",
          },
        };
      },
    }),
  };
}
