/* Copyright 2026 Marimo. All rights reserved. */

import { NotebookEvents, StreamStopped } from "@marimo-team/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createNotebookTransport,
  pyodide,
  sessionSse,
  websocket,
} from "../notebook";

const wasm = vi.hoisted(() => ({ enabled: false, consumer: vi.fn() }));
vi.mock("../../../wasm/utils", () => ({ isWasm: () => wasm.enabled }));
vi.mock("../../../wasm/bridge", () => ({
  PyodideBridge: { INSTANCE: { attachMessageConsumer: wasm.consumer } },
}));

const encoder = new TextEncoder();

/** A WebSocket the test drives. */
class FakeSocket extends EventTarget {
  public static readonly opened: FakeSocket[] = [];
  public readonly url: string;
  public constructor(url: URL) {
    super();
    this.url = String(url);
    FakeSocket.opened.push(this);
  }
  public open() {
    this.dispatchEvent(new Event("open"));
  }
  public receive(text: string) {
    this.dispatchEvent(new MessageEvent("message", { data: text }));
  }
  public close(code = 1006, reason = "") {
    this.dispatchEvent(Object.assign(new Event("close"), { code, reason }));
  }
}

/** An SSE response body the test writes to. */
function body() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  return {
    response: new Response(stream, {
      headers: { "Content-Type": "text/event-stream" },
    }),
    push: (text: string) => controller.enqueue(encoder.encode(text)),
    end: () => controller.close(),
  };
}

function collect(events: NotebookEvents<string>) {
  const received: unknown[] = [];
  events.subscribe((event) => received.push(event));
  return received;
}

afterEach(() => {
  FakeSocket.opened.length = 0;
  wasm.enabled = false;
  wasm.consumer.mockReset();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("websocket", () => {
  it("resumes with the cursor and reads data with marimo's parser", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", FakeSocket);
    const events = new NotebookEvents(
      websocket(() => "ws://localhost/ws?session_id=s1&cursor=stale"),
      { types: ["marimo"] },
    );
    const received = collect(events);
    await vi.waitFor(() => expect(FakeSocket.opened).toHaveLength(1));
    const [first] = FakeSocket.opened;
    first.open();
    first.receive(
      '{"event":"marimo","id":"7","data":{"marimo":{"value":NaN}}}',
    );
    first.close();
    await vi.advanceTimersByTimeAsync(2000);
    expect(FakeSocket.opened.map((socket) => socket.url))
      .toMatchInlineSnapshot(`
      [
        "ws://localhost/ws?session_id=s1",
        "ws://localhost/ws?session_id=s1&cursor=7",
      ]
    `);
    expect(received).toEqual([
      { event: "marimo", id: "7", data: { marimo: { value: Number.NaN } } },
    ]);
    events.close();
  });

  it("stops on a close the editor treats as final, with its status", async () => {
    vi.stubGlobal("WebSocket", FakeSocket);
    const events = new NotebookEvents(websocket(() => "ws://localhost/ws"));
    await vi.waitFor(() => expect(FakeSocket.opened).toHaveLength(1));
    FakeSocket.opened[0].open();
    FakeSocket.opened[0].close(3000, "MARIMO_UNAUTHORIZED");
    const error = await events.closed.catch((error: unknown) => error);
    expect(error).toBeInstanceOf(StreamStopped);
    expect((error as StreamStopped).cause).toMatchInlineSnapshot(`
      {
        "code": "KERNEL_DISCONNECTED",
        "reason": "not authorized",
        "state": "CLOSED",
      }
    `);
  });

  it("passes on a message it cannot read for the stream to reject", async () => {
    vi.stubGlobal("WebSocket", FakeSocket);
    const events = new NotebookEvents(websocket(() => "ws://localhost/ws"));
    await vi.waitFor(() => expect(FakeSocket.opened).toHaveLength(1));
    FakeSocket.opened[0].open();
    FakeSocket.opened[0].receive("{broken");
    await expect(events.closed).rejects.toThrow("not an event");
  });

  it("retries a socket that never opens", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", FakeSocket);
    const events = new NotebookEvents(websocket(() => "ws://localhost/ws"));
    await vi.waitFor(() => expect(FakeSocket.opened).toHaveLength(1));
    await vi.advanceTimersByTimeAsync(10_000 + 2000);
    expect(FakeSocket.opened).toHaveLength(2);
    events.close();
  });
});

describe("sessionSse", () => {
  it("sends the runtime's headers and the cursor with each request", async () => {
    vi.useFakeTimers();
    const first = body();
    const fetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => first.response,
    );
    vi.stubGlobal("fetch", fetch);
    let token = "a";
    const events = new NotebookEvents(
      sessionSse(
        () => "http://localhost/sse?session_id=s1",
        () => ({ "Marimo-Server-Token": token }),
      ),
    );
    first.push("id: 9\nevent: ready\ndata: {}\n\n");
    await vi.waitFor(() => expect(events.cursor).toBe("9"));
    token = "b";
    first.end();
    fetch.mockImplementation(async () => body().response);
    await vi.advanceTimersByTimeAsync(2000);
    const requests = fetch.mock.calls.map(
      ([input, init]) => new Request(input, init),
    );
    expect(
      requests.map((request) => ({
        url: request.url,
        token: request.headers.get("Marimo-Server-Token"),
        cursor: request.headers.get("Last-Event-ID"),
      })),
    ).toMatchInlineSnapshot(`
      [
        {
          "cursor": null,
          "token": "a",
          "url": "http://localhost/sse?session_id=s1",
        },
        {
          "cursor": "9",
          "token": "b",
          "url": "http://localhost/sse?session_id=s1",
        },
      ]
    `);
    events.close();
  });

  it("stops on a session close frame the editor treats as final", async () => {
    const stream = body();
    vi.stubGlobal("fetch", async () => stream.response);
    const events = new NotebookEvents(
      sessionSse(
        () => "http://localhost/sse",
        () => ({}),
      ),
    );
    stream.push(
      'event: close\ndata: {"code":1000,"reason":"MARIMO_SHUTDOWN"}\n\n',
    );
    const error = await events.closed.catch((error: unknown) => error);
    expect((error as StreamStopped).cause).toMatchInlineSnapshot(`
      {
        "code": "KERNEL_DISCONNECTED",
        "reason": "kernel not found",
        "state": "CLOSED",
      }
    `);
  });

  it("reads data with marimo's parser", async () => {
    const stream = body();
    vi.stubGlobal("fetch", async () => stream.response);
    const events = new NotebookEvents(
      sessionSse(
        () => "http://localhost/sse",
        () => ({}),
      ),
      { types: ["marimo"] },
    );
    const received = collect(events);
    stream.push('event: marimo\ndata: {"marimo":{"value":NaN}}\n\n');
    await vi.waitFor(() => expect(received).toHaveLength(1));
    expect(received).toEqual([
      { event: "marimo", data: { marimo: { value: Number.NaN } } },
    ]);
    events.close();
  });
});

describe("pyodide", () => {
  it("delivers worker notifications as marimo events and host events as they are", async () => {
    let consumer: ((message: MessageEvent<string>) => void) | undefined;
    const events = new NotebookEvents(
      pyodide((next) => {
        consumer = next;
      }),
      { types: ["notebook", "marimo"] },
    );
    const received = collect(events);
    await vi.waitFor(() => expect(consumer).toBeDefined());
    const send = (data: string) =>
      consumer?.(new MessageEvent("message", { data }));
    send('{"data":{"op":"kernel-ready"}}');
    send('{"event":"marimo","id":"3","data":{"marimo":{"op":"reconnected"}}}');
    expect(received).toMatchInlineSnapshot(`
      [
        {
          "data": {
            "marimo": {
              "op": "kernel-ready",
            },
          },
          "event": "marimo",
        },
        {
          "data": {
            "marimo": {
              "op": "reconnected",
            },
          },
          "event": "marimo",
          "id": "3",
        },
      ]
    `);
    events.close();
  });
});

describe("createNotebookTransport", () => {
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
    vi.stubGlobal("fetch", fetch);
    vi.stubGlobal("WebSocket", FakeSocket);
    const events = new NotebookEvents(createNotebookTransport(chosen));
    await vi.waitFor(() =>
      expect(
        {
          idle:
            events.status === "connected" && !wasm.consumer.mock.calls.length,
          wasm: wasm.consumer.mock.calls.length === 1,
          fetch: fetch.mock.calls.length === 1,
          socket: FakeSocket.opened.length === 1,
        }[expected],
      ).toBe(true),
    );
    events.close();
  });
});
