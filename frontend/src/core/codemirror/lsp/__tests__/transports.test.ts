/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import { store } from "@/core/state/jotai";
import { createTransport } from "../transports";

vi.mock("../../../network/connection", () => ({
  waitForConnectionOpen: vi.fn(() => Promise.resolve()),
}));

vi.mock("../../../runtime/config", () => ({
  getRuntimeManager: () => ({
    getLSPURL: (server: string) => new URL(`ws://localhost:2718/lsp/${server}`),
  }),
}));

/** Minimal stand-in for the browser WebSocket used by `WebSocketTransport`. */
class FakeWebSocket {
  static readonly instances: FakeWebSocket[] = [];
  static readonly OPEN = 1;

  readyState = 0;
  readonly url: string;
  private readonly listeners = new Map<string, Set<(event: unknown) => void>>();

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: (event: unknown) => void) {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  send() {
    // no-op
  }

  close() {
    this.readyState = 3;
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.emit("open", {});
  }

  receive(message: unknown) {
    this.emit("message", { data: JSON.stringify(message) });
  }

  private emit(type: string, event: unknown) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

describe("createTransport", () => {
  beforeEach(() => {
    FakeWebSocket.instances.length = 0;
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.spyOn(console, "log").mockImplementation(() => undefined);
    store.set(notebookAtom, initialNotebookState());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("forwards window/logMessage notifications to the logs panel", async () => {
    const transport = createTransport("pylsp");
    const connected = transport.connect();
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const socket = FakeWebSocket.instances[0];
    socket.open();
    await connected;

    socket.receive({
      jsonrpc: "2.0",
      method: "window/logMessage",
      params: { type: 1, message: "pylsp failed to start" },
    });
    socket.receive({
      jsonrpc: "2.0",
      method: "window/logMessage",
      params: { type: 3, message: "indexing workspace" },
    });
    // Unrelated notifications are left alone.
    socket.receive({
      jsonrpc: "2.0",
      method: "textDocument/publishDiagnostics",
      params: { uri: "file:///a", diagnostics: [] },
    });

    expect(store.get(notebookAtom).cellLogs).toMatchObject([
      {
        level: "stderr",
        message: "pylsp failed to start",
        source: { type: "lsp", name: "pylsp" },
      },
      {
        level: "stdout",
        message: "indexing workspace",
        source: { type: "lsp", name: "pylsp" },
      },
    ]);
  });
});
