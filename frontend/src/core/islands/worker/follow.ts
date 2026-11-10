/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai/vanilla";
import { createNotebookAutorun } from "@/core/executions/autorun";
import { createNotebookReplica } from "@/core/notebook/replica";
import { createWasmNotebookBackend } from "@/core/transports/wasm";
import type { SerializedBridge } from "@/core/wasm/worker/types";
import { Deferred } from "@/utils/Deferred";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";

/** Follow one island session; the same replica and autorun logic serve the editor. */
export async function followIsland({
  bridge,
  sessionGeneration,
  signal,
  emit,
  onError,
}: {
  bridge: {
    readonly notebook: Pick<
      SerializedBridge["notebook"],
      "id" | "subscribe" | "unsubscribe" | "call" | "destroy"
    >;
  };
  sessionGeneration: number;
  signal: AbortSignal;
  emit: (event: string) => void;
  onError: (error: unknown) => void;
}): Promise<void> {
  signal.throwIfAborted();
  const subscribed = new Deferred<void>();
  const store = createStore();
  const replica = createNotebookReplica(store);
  const backend = createWasmNotebookBackend({
    subscribe: async (cursor, message) => {
      const notebook = bridge.notebook;
      const id = `island-${sessionGeneration}`;
      try {
        await notebook.subscribe(id, cursor, (raw) => {
          emit(raw);
          message(jsonParseWithSpecialChar(raw));
        });
        subscribed.resolve();
        return () => {
          const notebook = bridge.notebook;
          try {
            notebook.unsubscribe(id);
          } finally {
            notebook.destroy();
          }
        };
      } catch (error) {
        subscribed.reject(error);
        throw error;
      } finally {
        notebook.destroy();
      }
    },
    call: async (call) => {
      const notebook = bridge.notebook;
      try {
        return JSON.parse(await notebook.call(JSON.stringify(call)));
      } finally {
        notebook.destroy();
      }
    },
  });
  const disconnect = replica.connect(backend, {
    onNotification: () => undefined,
  });
  signal.addEventListener("abort", disconnect, { once: true });
  createNotebookAutorun({ store, replica }).start({
    autoRun: true,
    signal,
    onError,
  });
  await subscribed.promise;
}
