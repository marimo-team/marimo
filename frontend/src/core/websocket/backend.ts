/* Copyright 2026 Marimo. All rights reserved. */

/** The backend the editor follows, chosen once for its mode. */

import { NotebookClient, StreamStopped } from "@marimo-team/client";
import type { NotebookId } from "@marimo-team/client/protocol";
import type { NotebookBackend } from "../host";
import { PyodideBridge } from "../wasm/bridge";
import { isWasm } from "../wasm/utils";
import {
  idle,
  sessionSse,
  websocket,
  withHeaders,
} from "./transports/notebook";

/** How the editor follows its notebook. */
export interface EditorBackendOptions {
  static: boolean;
  transportType: "websocket" | "sse";
  /** The session route, read before each connection. */
  url: () => string;
  /** The runtime's headers, read before each request. */
  headers: () => Record<string, string>;
  /** The host URL of a notebook the stream reported. */
  notebookUrl: (notebookId: NotebookId) => URL;
  /** Wait until the host can accept the first connection. */
  waitUntilReady: () => Promise<void>;
  /** Whether the host is reachable before an explicit reconnect. */
  checkHealth: () => Promise<boolean>;
}

/**
 * Read the session route once the host has started.
 *
 * Every connection waits for the same startup. Once it settles, even by
 * giving up, connections read the route directly. An explicit reconnect
 * checks the host's health instead.
 */
function afterStartup({
  url,
  waitUntilReady,
}: Pick<EditorBackendOptions, "url" | "waitUntilReady">) {
  let startup: Promise<void> | undefined;
  let settled = false;
  return async () => {
    if (!settled) {
      startup ??= waitUntilReady().finally(() => {
        settled = true;
      });
      try {
        await startup;
      } catch (error) {
        throw new StreamStopped("Healthy connection never made", {
          cause: error,
        });
      }
    }
    return url();
  };
}

/**
 * Follow the notebook running in the WASM worker.
 *
 * The worker's backend exists once the worker has started, so the first
 * connection creates it. Commands are only for a notebook its stream reported.
 */
function wasm(): NotebookBackend {
  let backend: Promise<NotebookBackend> | undefined;
  let started: NotebookBackend | undefined;
  return {
    transport: async (attempt, handlers) => {
      backend ??= PyodideBridge.INSTANCE.createNotebookBackend();
      try {
        started = await backend;
      } catch (error) {
        throw new StreamStopped("The WASM notebook did not start", {
          cause: error,
        });
      }
      return started.transport(attempt, handlers);
    },
    notebook: (id) => {
      if (started === undefined) {
        throw new Error("The WASM notebook has not started");
      }
      return started.notebook(id);
    },
  };
}

/** Commands for a notebook the editor cannot change through its backend. */
function uneditable(): ReturnType<NotebookBackend["notebook"]> {
  const unsupported: NotebookClient["save"] = async () => ({
    ok: false,
    status: 501,
    problem: {
      type: "tag:marimo.io,2026:host/unsupported-operation",
      title: "Document mutations are unavailable on this connection",
      status: 501,
    },
  });
  return { edit: () => unsupported(), save: unsupported };
}

/** Choose the backend for the editor's notebook. */
export function createEditorBackend(
  options: EditorBackendOptions,
): NotebookBackend {
  if (options.static) {
    return { transport: idle, notebook: uneditable };
  }
  if (isWasm()) {
    return wasm();
  }
  const url = afterStartup(options);
  return {
    transport:
      options.transportType === "sse"
        ? sessionSse(url, options.headers)
        : websocket(url),
    notebook: (id) =>
      new NotebookClient(options.notebookUrl(id), {
        fetch: withHeaders(options.headers),
      }),
    checkHealth: options.checkHealth,
  };
}
