/* Copyright 2026 Marimo. All rights reserved. */

/** A backend for the notebook running in the WASM worker. */

import {
  NotebookClient,
  StreamStopped,
  type unstable_NotebookCall,
} from "@marimo-team/client";
import type { NotebookBackend } from "./backend";

/** The worker owns the notebook; this interface only carries commands and events. */
export interface WasmNotebookBridge {
  readonly notebookId: string;
  subscribe(
    cursor: string | null,
    emit: (event: unknown) => void,
    signal: AbortSignal,
  ): Promise<() => void>;
  /** Deliver a call to the worker and resolve with its status and body. */
  call(call: unstable_NotebookCall): Promise<unknown>;
}

/** Stop waiting on cancellation; a command already sent may still commit. */
function abortable<T>(
  send: () => Promise<T>,
  signal?: AbortSignal,
): Promise<T> {
  if (!signal) {
    return send();
  }
  signal.throwIfAborted();
  return new Promise((resolve, reject) => {
    const abort = () => reject(signal.reason);
    signal.addEventListener("abort", abort, { once: true });
    send()
      .then(resolve, reject)
      .finally(() => signal.removeEventListener("abort", abort));
  });
}

export function createWasmNotebookBackend(
  bridge: WasmNotebookBridge,
): NotebookBackend {
  const client = NotebookClient.unstable_over((call) => bridge.call(call), {
    notebookId: bridge.notebookId,
  });
  return {
    transport: async ({ cursor, signal }, { open, message }) => {
      if (signal.aborted) {
        return;
      }
      let unsubscribe: (() => void) | undefined;
      let finish!: () => void;
      const closed = new Promise<void>((resolve) => {
        finish = resolve;
      });
      const abort = () => {
        unsubscribe?.();
        finish();
      };
      signal.addEventListener("abort", abort, { once: true });
      try {
        open();
        // Keep the pending subscription so a close during startup still releases it.
        await abortable(
          () =>
            bridge
              .subscribe(
                cursor,
                (event) => {
                  if (!signal.aborted) {
                    message(event);
                  }
                },
                signal,
              )
              .then((close) => {
                unsubscribe = close;
                if (signal.aborted) {
                  close();
                }
              }),
          signal,
        );
        await closed;
      } catch (error) {
        if (!signal.aborted) {
          unsubscribe?.();
          throw new StreamStopped("Could not follow the WASM notebook", {
            cause: error,
          });
        }
      } finally {
        signal.removeEventListener("abort", abort);
      }
    },
    notebook: (id) => {
      if (id !== bridge.notebookId) {
        throw new Error(
          `The worker serves notebook ${bridge.notebookId}, not ${id}`,
        );
      }
      return client;
    },
  };
}
