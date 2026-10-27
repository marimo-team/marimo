/* Copyright 2026 Marimo. All rights reserved. */

import { NotebookClient, StreamStopped } from "@marimo-team/client";
import type { NotebookId } from "@marimo-team/client/protocol";
import type { NotebookBackend } from "../host/backend";
import { PyodideBridge } from "../wasm/bridge";
import { isWasm } from "../wasm/utils";
import {
  idle,
  pyodide,
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

/** Commands for a notebook the editor cannot change through its backend. */
function uneditable(): ReturnType<NotebookBackend["notebook"]> {
  return {
    edit: async () => ({
      ok: false,
      status: 501,
      problem: {
        type: "tag:marimo.io,2026:host/unsupported-operation",
        title: "Document editing is unavailable on this connection",
        status: 501,
      },
    }),
  };
}

/** Choose the backend for the editor's notebook. */
export function createEditorBackend(
  options: EditorBackendOptions,
): NotebookBackend {
  if (options.static) {
    return { transport: idle, notebook: uneditable };
  }
  if (isWasm()) {
    return {
      transport: pyodide((consumer) =>
        PyodideBridge.INSTANCE.attachMessageConsumer(consumer),
      ),
      notebook: uneditable,
    };
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
