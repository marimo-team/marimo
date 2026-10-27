/* Copyright 2026 Marimo. All rights reserved. */

import { NotebookEvents } from "@marimo-team/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createEditorBackend } from "../backend";

const wasm = vi.hoisted(() => ({ enabled: false, consumer: vi.fn() }));
vi.mock("../../wasm/utils", () => ({ isWasm: () => wasm.enabled }));
vi.mock("../../wasm/bridge", () => ({
  PyodideBridge: { INSTANCE: { attachMessageConsumer: wasm.consumer } },
}));

afterEach(() => {
  wasm.enabled = false;
  wasm.consumer.mockReset();
  vi.unstubAllGlobals();
});

describe("createEditorBackend", () => {
  const options = {
    static: false,
    transportType: "websocket" as const,
    url: () => "ws://localhost/ws",
    headers: () => ({}),
  };

  it.each([
    ["a static notebook", { ...options, static: true }, "idle"],
    ["WASM", options, "wasm"],
    ["SSE", { ...options, transportType: "sse" as const }, "fetch"],
    ["the default", options, "socket"],
  ] as const)("follows %s", async (_name, chosen, expected) => {
    wasm.enabled = expected === "wasm";
    const fetch = vi.fn(() => new Promise<Response>(() => undefined));
    const socket = vi.fn();
    vi.stubGlobal("fetch", fetch);
    vi.stubGlobal(
      "WebSocket",
      class extends EventTarget {
        public constructor(url: URL) {
          super();
          socket(url);
        }
        public close() {}
      },
    );
    const events = new NotebookEvents(createEditorBackend(chosen).transport);
    await vi.waitFor(() =>
      expect(
        {
          idle:
            events.status === "connected" && !wasm.consumer.mock.calls.length,
          wasm: wasm.consumer.mock.calls.length === 1,
          fetch: fetch.mock.calls.length === 1,
          socket: socket.mock.calls.length === 1,
        }[expected],
      ).toBe(true),
    );
    events.close();
  });
});
