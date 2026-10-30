/* Copyright 2026 Marimo. All rights reserved. */

/** A backend that serves a document snapshot without a host. */

import type { NotebookClient } from "@marimo-team/client";
import type * as Protocol from "@marimo-team/client/protocol";
import type { NotebookBackend } from "../notebook/replica";

/** A document snapshot with its own identity and revision metadata. */
export interface StaticNotebookSnapshot {
  readonly notebook: Omit<Protocol.Notebook, "operations">;
  readonly document: Protocol.Document;
  readonly cells: readonly Protocol.Cell[];
}

/** The events that describe a snapshot, in the order a host sends them. */
function snapshotFrames(snapshot: StaticNotebookSnapshot): Protocol.Event[] {
  return [
    {
      event: "notebook",
      data: { notebook: { ...snapshot.notebook, operations: [] } },
    },
    ...snapshot.cells.map((cell): Protocol.CellEvent => ({
      event: "cell",
      data: { cell },
    })),
    { event: "document", data: { document: snapshot.document } },
  ];
}

/** A snapshot of a notebook with no cells. */
export function emptySnapshot(notebookId: string): StaticNotebookSnapshot {
  return {
    notebook: {
      id: notebookId,
      project_id: notebookId,
      path: null,
      name: "",
      updated_at: null,
    },
    document: {
      notebook_id: notebookId,
      order: [],
      app_config: {},
      etag: `${notebookId}:document`,
      saved_etag: `${notebookId}:document`,
      order_etag: `${notebookId}:order`,
      app_config_etag: `${notebookId}:app_config`,
      version: 1,
    },
    cells: [],
  };
}

/**
 * Show a snapshot until `live` answers.
 *
 * The page carries the notebook it was served with, so cells appear before
 * the host connects. The snapshot ends in a `ready` of its own, like a
 * static notebook's, so the replica publishes it. At the host's first sign
 * of life a `reset` discards it, and the host's snapshot takes over. A
 * connection that resumes from a host cursor skips the snapshot; one that
 * resumes from the snapshot's cursor starts the host connection fresh,
 * since the host never issued it.
 */
export function startWithSnapshot(
  snapshot: StaticNotebookSnapshot,
  live: NotebookBackend,
): NotebookBackend {
  const cursor = `${snapshot.notebook.id}:snapshot`;
  return {
    ...live,
    transport: (attempt, handlers) => {
      if (attempt.cursor !== null && attempt.cursor !== cursor) {
        return live.transport(attempt, handlers);
      }
      if (attempt.cursor === null) {
        for (const frame of snapshotFrames(snapshot)) {
          if (attempt.signal.aborted) {
            break;
          }
          handlers.message(frame);
        }
        if (!attempt.signal.aborted) {
          handlers.message({ event: "ready", id: cursor, data: {} });
        }
      }
      let shown = true;
      const discard = () => {
        if (shown) {
          shown = false;
          handlers.message({ event: "reset", data: {} });
        }
      };
      return live.transport(
        { ...attempt, cursor: null },
        {
          open: () => {
            discard();
            handlers.open();
          },
          message: (frame) => {
            discard();
            handlers.message(frame);
          },
        },
      );
    },
  };
}

/**
 * Serve a document without a server, runtime, or mutation operations.
 * Callers and readers must treat the snapshot records as immutable.
 */
export function createStaticNotebookBackend(
  snapshot: StaticNotebookSnapshot,
): NotebookBackend {
  const frames: Protocol.Event[] = [
    ...snapshotFrames(snapshot),
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
    notebook: () => {
      const unsupported: NotebookClient["save"] = async (options) => {
        options?.signal?.throwIfAborted();
        return {
          ok: false,
          status: 501,
          problem: {
            type: "tag:marimo.io,2026:host/unsupported-operation",
            title: "Unsupported operation",
            status: 501,
            detail: "Static notebooks do not support mutations",
          },
        };
      };
      return {
        edit: (_changes, options) => unsupported(options),
        save: unsupported,
      };
    },
  };
}
