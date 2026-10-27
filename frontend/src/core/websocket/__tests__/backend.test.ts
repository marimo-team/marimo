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
    notebookUrl: (id: string) =>
      new URL(`http://localhost/api/marimo/v1/notebooks/${id}`),
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

  it("edits a reported notebook on its host with the session's headers", async () => {
    const fetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response(
          JSON.stringify({ type: "conflict", title: "Conflict", status: 409 }),
          {
            status: 409,
            headers: { "Content-Type": "application/problem+json" },
          },
        ),
    );
    vi.stubGlobal("fetch", fetch);
    const backend = createEditorBackend({
      ...options,
      headers: () => ({
        Authorization: "Bearer editor-token",
        "Marimo-Server-Token": "server-token",
      }),
    });
    const result = await backend
      .notebook("n1")
      .edit([], { idempotencyKey: "edit-1" });
    expect(result).toMatchObject({ ok: false, status: 409 });
    const [[input, init]] = fetch.mock.calls;
    expect(String(input)).toBe(
      "http://localhost/api/marimo/v1/notebooks/n1/edits",
    );
    const headers = new Headers(init?.headers);
    expect(init?.method).toBe("POST");
    expect(headers.get("Authorization")).toBe("Bearer editor-token");
    expect(headers.get("Marimo-Server-Token")).toBe("server-token");
    expect(headers.get("Idempotency-Key")).toBe("edit-1");
  });

  it.each([
    ["a static notebook", { ...options, static: true }, false],
    ["WASM", options, true],
  ] as const)("does not edit %s", async (_name, chosen, isWasm) => {
    wasm.enabled = isWasm;
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const result = await createEditorBackend(chosen)
      .notebook("n1")
      .edit([], { idempotencyKey: "edit-1" });
    expect(result).toMatchObject({ ok: false, status: 501 });
    expect(fetch).not.toHaveBeenCalled();
  });
});
