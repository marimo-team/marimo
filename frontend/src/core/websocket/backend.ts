/* Copyright 2026 Marimo. All rights reserved. */

import { NotebookClient, type StreamUrl } from "@marimo-team/client";
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
  url: StreamUrl;
  /** The runtime's headers, read before each request. */
  headers: () => Record<string, string>;
  /** The host URL of a notebook the stream reported. */
  notebookUrl: (notebookId: NotebookId) => URL;
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
  return {
    transport:
      options.transportType === "sse"
        ? sessionSse(options.url, options.headers)
        : websocket(options.url),
    notebook: (id) =>
      new NotebookClient(options.notebookUrl(id), {
        fetch: withHeaders(options.headers),
      }),
  };
}
