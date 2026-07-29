/* Copyright 2026 Marimo. All rights reserved. */

import type { JSONRPCMessage } from "@marimo-team/codemirror-languageserver";
import { beforeEach, describe, expect, it } from "vitest";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import { store } from "@/core/state/jotai";
import { handleLogMessage } from "../log-messages";

function logMessage(type: number, message: string): JSONRPCMessage {
  return {
    jsonrpc: "2.0",
    method: "window/logMessage",
    params: { type, message },
  } as JSONRPCMessage;
}

describe("handleLogMessage", () => {
  beforeEach(() => {
    store.set(notebookAtom, initialNotebookState());
  });

  it("adds a log for each message, erroring on Error and Warning", () => {
    handleLogMessage("pylsp", logMessage(1, "failed to start"));
    handleLogMessage("pylsp", logMessage(2, "plugin not installed"));
    handleLogMessage("pylsp", logMessage(3, "indexing"));

    expect(store.get(notebookAtom).cellLogs).toMatchObject([
      { level: "stderr", message: "failed to start" },
      { level: "stderr", message: "plugin not installed" },
      {
        level: "stdout",
        message: "indexing",
        source: { type: "lsp", name: "pylsp" },
      },
    ]);
  });

  it("ignores messages that aren't logs", () => {
    handleLogMessage("pylsp", { jsonrpc: "2.0", id: 1 } as JSONRPCMessage);
    handleLogMessage("pylsp", {
      jsonrpc: "2.0",
      method: "textDocument/publishDiagnostics",
      params: { uri: "file:///a", diagnostics: [] },
    } as JSONRPCMessage);
    handleLogMessage("pylsp", {
      jsonrpc: "2.0",
      method: "window/logMessage",
      params: { type: 1 },
    } as JSONRPCMessage);

    expect(store.get(notebookAtom).cellLogs).toEqual([]);
  });
});
