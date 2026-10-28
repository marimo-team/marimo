/* Copyright 2026 Marimo. All rights reserved. */

import {
  NotebookEvents,
  StreamStopped,
  type StreamUrl,
} from "@marimo-team/client";
import { createStore } from "jotai/vanilla";
import { afterEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { createNotebookReplica } from "../../../host/replica";
import { fakeBackend, fixtureMessages } from "../../../host/__tests__/fixtures";
import { ConnectionState } from "../../../host/connection";
import { Deferred } from "@/utils/Deferred";
import { sessionSse, websocket } from "../notebook";

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

/** Drive the real session adapter through either network protocol. */
function network(transportType: "websocket" | "sse", url: StreamUrl) {
  const requests: { request: Request; stream: ReturnType<typeof body> }[] = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal(
    "fetch",
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const stream = body();
      requests.push({ request: new Request(input, init), stream });
      return stream.response;
    },
  );
  const count = () =>
    transportType === "websocket" ? FakeSocket.opened.length : requests.length;
  const transport =
    transportType === "websocket"
      ? websocket(url)
      : sessionSse(url, () => ({}));
  const backend = fakeBackend({ transport });
  let index = 0;
  return {
    backend,
    transport,
    count,
    opened: async () => {
      await vi.waitFor(() => expect(count()).toBeGreaterThan(index));
      const next = index++;
      if (transportType === "websocket") {
        const socket = FakeSocket.opened[next];
        socket.open();
        return {
          cursor: new URL(socket.url).searchParams.get("cursor"),
          receive: (frame: { event: string; data: unknown; id?: string }) =>
            socket.receive(JSON.stringify(frame)),
          drop: () => socket.close(),
          stop: () => socket.close(1000, "MARIMO_SHUTDOWN"),
        };
      }
      const { request, stream } = requests[next];
      return {
        cursor: request.headers.get("Last-Event-ID"),
        receive: (frame: { event: string; data: unknown; id?: string }) =>
          stream.push(
            `${frame.id === undefined ? "" : `id: ${frame.id}\n`}event: ${frame.event}\ndata: ${JSON.stringify(frame.data)}\n\n`,
          ),
        drop: stream.end,
        stop: () =>
          stream.push(
            'event: close\ndata: {"code":1000,"reason":"MARIMO_SHUTDOWN"}\n\n',
          ),
      };
    },
  };
}

afterEach(() => {
  FakeSocket.opened.length = 0;
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

  it.each([
    ["NaN", Number.NaN],
    ["Infinity", Number.POSITIVE_INFINITY],
    ["-Infinity", Number.NEGATIVE_INFINITY],
    ['{"$bigint":"9007199254740993"}', BigInt("9007199254740993")],
  ])("reads %s with marimo's parser", async (encoded, value) => {
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
    onTestFinished(() => events.close());
    stream.push(`event: marimo\ndata: {"marimo":{"value":${encoded}}}\n\n`);
    await vi.waitFor(() => expect(received).toHaveLength(1));
    expect(received).toEqual([
      { event: "marimo", data: { marimo: { value } } },
    ]);
  });
});

describe.each(["websocket", "sse"] as const)(
  "%s session identity",
  (transportType) => {
    const base =
      transportType === "websocket"
        ? "ws://localhost/ws"
        : "http://localhost/sse";

    it.each(["automatic", "manual"])(
      "discards the cursor and replica when the session changes on %s reconnect",
      async (recovery) => {
        vi.useFakeTimers();
        let target = `${base}?session_id=s1`;
        const url = vi.fn(() => target);
        const connection = network(transportType, url);
        const store = createStore();
        const client = createNotebookReplica(store);
        onTestFinished(
          client.connect(connection.backend, { onNotification: vi.fn() }),
        );
        const first = await connection.opened();
        const snapshot = fixtureMessages("notebook-events.sse");
        snapshot.forEach(first.receive);
        await vi.waitFor(() =>
          expect(store.get(client.notebookAtom)?.id).toBe("n1"),
        );

        target = `${base}?session_id=s2`;
        if (recovery === "automatic") {
          first.drop();
          await vi.advanceTimersByTimeAsync(2000);
        } else {
          first.stop();
          await vi.waitUntil(
            () =>
              store.get(client.connectionAtom).state === ConnectionState.CLOSED,
          );
          await client.reconnect();
        }
        const second = await connection.opened();
        expect({
          cursor: second.cursor,
          notebook: store.get(client.notebookAtom),
          document: store.get(client.documentAtom),
          attachments: store.get(client.attachmentsAtom),
        }).toEqual({
          cursor: null,
          notebook: null,
          document: null,
          attachments: [],
        });

        // A second drop before any records must not resurrect the library's old cursor.
        second.drop();
        await vi.advanceTimersByTimeAsync(2000);
        const third = await connection.opened();
        expect(third.cursor).toBeNull();
        for (const frame of snapshot) {
          third.receive({
            ...frame,
            data: JSON.parse(
              JSON.stringify(frame.data).replaceAll('"n1"', '"n2"'),
            ),
          });
        }
        await vi.waitFor(() =>
          expect(store.get(client.notebookAtom)?.id).toBe("n2"),
        );
        expect(store.get(client.documentAtom)?.revision.notebook_id).toBe("n2");
        expect(url).toHaveBeenCalledTimes(3);
      },
    );

    it("keeps the replica and cursor when only authentication and query ordering change", async () => {
      vi.useFakeTimers();
      let target = `${base}?session_id=s1&file=a.py&access_token=a`;
      const connection = network(transportType, () => target);
      const store = createStore();
      const client = createNotebookReplica(store);
      onTestFinished(
        client.connect(connection.backend, { onNotification: vi.fn() }),
      );
      const first = await connection.opened();
      fixtureMessages("notebook-events.sse").forEach(first.receive);
      await vi.waitFor(() =>
        expect(store.get(client.notebookAtom)?.id).toBe("n1"),
      );
      const document = store.get(client.documentAtom);
      const attachments = store.get(client.attachmentsAtom);

      target = `${base}?access_token=b&file=a.py&session_id=s1`;
      first.drop();
      await vi.advanceTimersByTimeAsync(2000);
      const second = await connection.opened();
      expect(second.cursor).toBe("97");
      expect(store.get(client.documentAtom)).toBe(document);
      second.receive({ event: "ready", id: "100", data: {} });
      await vi.waitFor(() =>
        expect(store.get(client.notebookAtom)?.id).toBe("n1"),
      );
      expect(store.get(client.attachmentsAtom)).toEqual(attachments);
    });

    it("does not open a connection after cancellation during URL resolution", async () => {
      vi.useFakeTimers();
      const target = new Deferred<string>();
      const url = vi.fn(() => target.promise);
      const connection = network(transportType, url);
      const events = new NotebookEvents(connection.transport);
      onTestFinished(() => events.close());
      const received = collect(events);
      await vi.waitFor(() => expect(url).toHaveBeenCalledOnce());
      events.close();
      target.resolve(base);
      await vi.advanceTimersByTimeAsync(0);
      expect({
        opened: connection.count(),
        events: received,
        status: events.status,
      }).toEqual({ opened: 0, events: [], status: "closed" });
    });
  },
);
