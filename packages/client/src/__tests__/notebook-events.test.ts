/* Copyright 2026 Marimo. All rights reserved. */

import NodeFs from "node:fs";
import NodeUrl from "node:url";
import { afterEach, describe, expect, expectTypeOf, it, vi } from "vitest";
import { z } from "zod";
import { NotebookClient } from "../notebook/client.ts";
import { NotebookEvents } from "../notebook/events.ts";
import type { NotebookEvent } from "../notebook/events.ts";
import { type NotebookTransport, StreamStopped } from "../transport/frame.ts";
import { ServerSentEventStream, sse } from "../transport/sse.ts";

const fixtures = new NodeUrl.URL(
  "../../../../protocols/host/fixtures/",
  import.meta.url,
);
const snapshot = NodeFs.readFileSync(
  new NodeUrl.URL("notebook-events.sse", fixtures),
  "utf8",
);
/** The fixture's frames up to and including `ready`. */
const throughReady = snapshot.slice(0, snapshot.indexOf("id: 96\n"));

const encoder = new TextEncoder();

/** A response body the test writes to. */
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

/** A fetch that answers each connection with the next response. */
function answering(...responses: Response[]) {
  const fetch = vi.fn(
    async (_input: RequestInfo | URL, _init?: RequestInit) => {
      const response = responses.shift();
      if (response === undefined) {
        return new Promise<Response>(() => undefined);
      }
      return response;
    },
  );
  const sent = (index: number) => new Request(...fetch.mock.calls[index]);
  return { fetch, sent };
}

/** A transport whose connections deliver an event and drop after `uptime`. */
function dropsAfter(uptime: number) {
  let opened = 0;
  const transport: NotebookTransport = (_attempt, { open, message }) => {
    opened += 1;
    open();
    message({ event: "marimo", data: {}, id: String(opened) });
    return new Promise((resolve) => setTimeout(resolve, uptime));
  };
  return { transport, opened: () => opened };
}

function collect<K extends string>(events: NotebookEvents<K>) {
  const received: NotebookEvent<K>[] = [];
  events.subscribe((event) => received.push(event));
  return received;
}

const url = "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1/events";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** Parse text chunks as a host would send them. */
async function parse(chunks: string[]) {
  const reader = new ReadableStream<string>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(chunk));
      controller.close();
    },
  })
    .pipeThrough(new ServerSentEventStream())
    .getReader();
  const frames = [];
  for (let read = await reader.read(); !read.done; read = await reader.read()) {
    frames.push(read.value);
  }
  return frames;
}

describe("ServerSentEventStream", () => {
  it("parses names, ids, multiline data, and comments across chunks", async () => {
    expect(
      await parse([
        ': ping\r\nevent: cell\ndata: {"a":',
        "\ndata: 1}\nid: 7\n\n",
        "data: plain text\n\n",
      ]),
    ).toMatchInlineSnapshot(`
      [
        {
          "data": {
            "a": 1,
          },
          "event": "cell",
          "id": "7",
        },
        {
          "data": "plain text",
          "event": "message",
        },
      ]
    `);
  });

  it("reads a CRLF split across chunks as one line break", async () => {
    expect(await parse(["event: cell\r", '\ndata: {"a":1}\r\n\r\n']))
      .toMatchInlineSnapshot(`
      [
        {
          "data": {
            "a": 1,
          },
          "event": "cell",
        },
      ]
    `);
  });
});

/** A fetch that never answers until it is aborted. */
function unanswered() {
  return vi.fn(
    (_input: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((_, reject) => {
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      }),
  );
}

describe("NotebookEvents", () => {
  it("follows one run", async () => {
    const { fetch, sent } = answering();
    const events = new NotebookEvents(url, { runId: "r1", fetch });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(sent(0).url).toBe(`${url}?run_id=r1`);
    events.close();
  });

  it("retries statuses that ask the client to try again", async () => {
    vi.useFakeTimers();
    const stream = body();
    const { fetch } = answering(
      new Response(null, { status: 429 }),
      stream.response,
    );
    const events = new NotebookEvents(url, { fetch });
    await vi.advanceTimersByTimeAsync(2000);
    stream.push(throughReady);
    await vi.waitFor(() => expect(events.cursor).toBe("95"));
    events.close();
  });

  it("stops when the host answers with something other than events", async () => {
    const events = new NotebookEvents(url, {
      fetch: answering(
        new Response("<html>", { headers: { "Content-Type": "text/html" } }),
      ).fetch,
    });
    await expect(events.closed).rejects.toThrow("not answer with an event");
  });

  it("retries a host that accepts the request but never answers", async () => {
    vi.useFakeTimers();
    const fetch = unanswered();
    const events = new NotebookEvents(url, { fetch });
    await vi.advanceTimersByTimeAsync(45_000 + 2000);
    expect(fetch).toHaveBeenCalledTimes(2);
    events.close();
  });

  it("delivers a snapshot through ready and records the cursor", async () => {
    const stream = body();
    const { fetch, sent } = answering(stream.response);
    const events = new NotebookEvents(url, {
      token: "secret",
      types: ["cell", "document"],
      fetch,
    });
    const received = collect(events);
    stream.push(throughReady);

    await vi.waitFor(() => expect(events.cursor).toBe("95"));
    expect(received.map((event) => event.event)).toMatchInlineSnapshot(`
      [
        "cell",
        "cell",
        "cell",
        "document",
        "ready",
      ]
    `);
    expect(events.status).toBe("connected");
    const request = sent(0);
    expect(request.url).toBe(`${url}?types=cell%2Cdocument`);
    expect(request.headers.get("Authorization")).toBe("Bearer secret");
    expect(request.headers.get("Last-Event-ID")).toBeNull();
    events.close();
    await expect(events.closed).resolves.toBeUndefined();
    expect(events.status).toBe("closed");
  });

  it("narrows events to the requested kinds", () => {
    const events = new NotebookEvents(url, {
      types: ["cell", "marimo"],
      fetch: answering().fetch,
    });
    events.close();
    expectTypeOf<NotebookEvent<"cell" | "marimo">["event"]>().toEqualTypeOf<
      "cell" | "cell.removed" | "ready" | "reset" | "marimo"
    >();
    events.subscribe((event) => {
      if (event.event === "cell") {
        expectTypeOf(event.data.cell.id).toBeString();
      } else if (event.event === "marimo") {
        expectTypeOf(event.data).toBeUnknown();
      }
    });
  });

  it("resumes from its cursor after the connection drops", async () => {
    vi.useFakeTimers();
    const first = body();
    const second = body();
    const { fetch, sent } = answering(first.response, second.response);
    const statuses: string[] = [];
    const events = new NotebookEvents(url, {
      fetch,
      onStatus: (status) => statuses.push(status),
    });
    first.push(snapshot);
    await vi.waitFor(() => expect(events.cursor).toBe("97"));
    first.end();
    await vi.advanceTimersByTimeAsync(2000);
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(sent(1).headers.get("Last-Event-ID")).toBe("97");
    expect(statuses).toMatchInlineSnapshot(`
      [
        "connected",
        "connecting",
        "connected",
      ]
    `);
    events.close();
  });

  it("gives up on a host that drops each connection soon after opening", async () => {
    vi.useFakeTimers();
    const { transport, opened } = dropsAfter(1000);
    const events = new NotebookEvents(transport, { types: ["marimo"] });
    await vi.advanceTimersByTimeAsync(200_000);
    expect(events.status).toBe("closed");
    expect(opened()).toBe(11);
  });

  it("keeps following a host whose connections stay up", async () => {
    vi.useFakeTimers();
    const { transport, opened } = dropsAfter(5000);
    const events = new NotebookEvents(transport, { types: ["marimo"] });
    await vi.advanceTimersByTimeAsync(200_000);
    expect(events.status).not.toBe("closed");
    expect(opened()).toBeGreaterThan(11);
    events.close();
  });

  it("ignores a connection that reports after its attempt ended", async () => {
    let late: Parameters<NotebookTransport>[1] | undefined;
    const transport: NotebookTransport = async (_attempt, handlers) => {
      late ??= handlers;
    };
    const statuses: string[] = [];
    const events = new NotebookEvents(transport, {
      types: ["marimo"],
      onStatus: (status) => statuses.push(status),
    });
    const received = collect(events);
    await vi.waitFor(() => expect(late).toBeDefined());
    // Let the attempt end. The stream is then waiting to reconnect.
    await new Promise((resolve) => setTimeout(resolve, 10));
    late?.open();
    late?.message({ event: "marimo", data: {}, id: "9" });
    expect(statuses).toEqual([]);
    expect(received).toEqual([]);
    expect(events.cursor).toBeNull();
    events.close();
  });

  it("delivers reset before replacing an interrupted snapshot", async () => {
    vi.useFakeTimers();
    const first = body();
    const second = body();
    const { fetch, sent } = answering(first.response, second.response);
    const events = new NotebookEvents(url, { types: ["cell"], fetch });
    const received = collect(events);
    first.push(throughReady.slice(0, throughReady.indexOf("event: document")));
    await vi.waitFor(() => expect(received).toHaveLength(3));
    first.end();
    await vi.advanceTimersByTimeAsync(2000);
    second.push(throughReady);
    await vi.waitFor(() => expect(events.cursor).toBe("95"));
    expect(sent(1).headers.get("Last-Event-ID")).toBeNull();
    expect(received.map((event) => event.event)).toMatchInlineSnapshot(`
      [
        "cell",
        "cell",
        "cell",
        "reset",
        "cell",
        "cell",
        "cell",
        "ready",
      ]
    `);
    events.close();
  });

  it("clears the cursor on reset and keeps it across unknown kinds", async () => {
    const stream = body();
    const events = new NotebookEvents(url, {
      types: ["marimo"],
      fetch: answering(stream.response).fetch,
    });
    const received = collect(events);
    stream.push(throughReady);
    stream.push("id: 98\nevent: future\ndata: {}\n\n");
    stream.push('id: 99\nevent: marimo\ndata: {"marimo":{"op":"x"}}\n\n');
    await vi.waitFor(() => expect(events.cursor).toBe("99"));
    stream.push("event: reset\ndata: {}\n\n");
    await vi.waitFor(() => expect(events.cursor).toBeNull());
    expect(received).toMatchInlineSnapshot(`
      [
        {
          "data": {},
          "event": "ready",
          "id": "95",
        },
        {
          "data": {
            "marimo": {
              "op": "x",
            },
          },
          "event": "marimo",
          "id": "99",
        },
        {
          "data": {},
          "event": "reset",
        },
      ]
    `);
    events.close();
  });

  it("stays connected through pings longer than the silence limit", async () => {
    vi.useFakeTimers();
    const stream = body();
    const { fetch } = answering(stream.response);
    const events = new NotebookEvents(url, { fetch });
    stream.push(throughReady);
    await vi.waitFor(() => expect(events.status).toBe("connected"));
    for (let i = 0; i < 6; i++) {
      await vi.advanceTimersByTimeAsync(15_000);
      stream.push(": ping\n\n");
    }
    expect(fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(46_000);
    expect(events.status).toBe("connecting");
    events.close();
  });

  it("stops with the problem when the host refuses the stream", async () => {
    const problem = {
      type: "tag:marimo.io,2026:host/not-found",
      title: "Not found",
      status: 404,
    };
    const events = new NotebookEvents(url, {
      fetch: answering(
        new Response(JSON.stringify(problem), {
          status: 404,
          headers: { "Content-Type": "application/problem+json" },
        }),
      ).fetch,
    });
    const error = await events.closed.catch((error: unknown) => error);
    expect(error).toBeInstanceOf(StreamStopped);
    expect((error as StreamStopped).cause).toEqual(problem);
    expect(events.status).toBe("closed");
  });

  it("tells subscribers why it stopped, unless they left or closed it", async () => {
    const refused = new Response(null, { status: 403 });
    const stopped = new NotebookEvents(url, {
      fetch: answering(refused).fetch,
    });
    const subscribed = vi.fn();
    const left = vi.fn();
    stopped.subscribe(() => undefined, subscribed);
    stopped.subscribe(() => undefined, left)();
    await stopped.closed.catch(() => undefined);
    const late = vi.fn();
    stopped.subscribe(() => undefined, late);
    const closed = new NotebookEvents(url, { fetch: answering().fetch });
    const closing = vi.fn();
    closed.subscribe(() => undefined, closing);
    closed.close();
    await closed.closed;
    expect(subscribed.mock.calls).toEqual([[expect.any(StreamStopped)]]);
    expect(left).not.toHaveBeenCalled();
    expect(late).not.toHaveBeenCalled();
    expect(closing).not.toHaveBeenCalled();
  });

  it.each([false, true])(
    "owns each registration of a shared event callback (onError: %s)",
    async (withError) => {
      const stream = body();
      const events = new NotebookEvents(url, {
        types: ["marimo"],
        fetch: answering(stream.response).fetch,
      });
      const received = vi.fn();
      const leave = events.subscribe(received, withError ? vi.fn() : undefined);
      events.subscribe(received);
      leave();
      leave();
      stream.push("id: 1\nevent: marimo\ndata: {}\n\n");
      await vi.waitFor(() => expect(events.cursor).toBe("1"));
      events.close();
      expect(received.mock.calls).toEqual([
        [{ event: "marimo", data: {}, id: "1" }],
      ]);
    },
  );

  it("owns each registration of a shared error callback", async () => {
    const events = new NotebookEvents(url, {
      fetch: answering(new Response(null, { status: 403 })).fetch,
    });
    const failed = vi.fn();
    const leave = events.subscribe(vi.fn(), failed);
    events.subscribe(vi.fn(), failed);
    leave();
    events.subscribe(vi.fn(), failed);
    leave();
    const error = await events.closed.catch((error: unknown) => error);
    expect(failed.mock.calls).toEqual([[error], [error]]);
  });

  it.each(["status", "error"])(
    "honors unsubscribe during terminal %s delivery",
    async (during) => {
      let leave = () => {};
      const events = new NotebookEvents(url, {
        fetch: answering(new Response(null, { status: 403 })).fetch,
        onStatus: (status) => {
          if (status === "closed" && during === "status") {
            leave();
          }
        },
      });
      events.subscribe(vi.fn(), () => {
        if (during === "error") {
          leave();
        }
      });
      const removed = vi.fn();
      const remaining = vi.fn();
      leave = events.subscribe(vi.fn(), removed);
      events.subscribe(vi.fn(), remaining);
      const error = await events.closed.catch((error: unknown) => error);
      expect(removed.mock.calls).toEqual([]);
      expect(remaining.mock.calls).toEqual([[error]]);
    },
  );

  it("reports a throwing error callback and still notifies other subscribers", async () => {
    const queued = vi.fn();
    vi.stubGlobal("queueMicrotask", queued);
    const thrown = new Error("subscriber failed");
    const events = new NotebookEvents(url, {
      fetch: answering(new Response(null, { status: 403 })).fetch,
    });
    events.subscribe(vi.fn(), () => {
      throw thrown;
    });
    const remaining = vi.fn();
    events.subscribe(vi.fn(), remaining);
    const error = await events.closed.catch((error: unknown) => error);
    expect(remaining.mock.calls).toEqual([[error]]);
    expect(queued.mock.calls).toEqual([[expect.any(Function)]]);
    expect(queued.mock.calls[0][0]).toThrow(thrown);
  });

  it("does not notify error subscribers when aborted", async () => {
    const controller = new AbortController();
    const events = new NotebookEvents(url, {
      signal: controller.signal,
      fetch: unanswered(),
    });
    const failed = vi.fn();
    events.subscribe(vi.fn(), failed);
    controller.abort();
    await expect(events.closed).resolves.toBeUndefined();
    expect(failed.mock.calls).toEqual([]);
  });

  it.each([
    'event: cell\ndata: {"cell":{"id":"c1"}}\n\n',
    "event: reset\ndata: 5\n\n",
  ])("stops on an invalid protocol event: %j", async (frame) => {
    const stream = body();
    const events = new NotebookEvents(url, {
      fetch: answering(stream.response).fetch,
    });
    stream.push(frame);
    await expect(events.closed).rejects.toThrow(/invalid (cell|reset) event/);
  });

  it("delivers nothing after it closes", async () => {
    const stream = body();
    const events = new NotebookEvents(url, {
      fetch: answering(stream.response).fetch,
    });
    const received = collect(events);
    events.close();
    stream.push(throughReady);
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(received).toEqual([]);
  });

  it("iterates until the caller leaves the loop", async () => {
    const stream = body();
    const events = new NotebookEvents(url, {
      types: ["cell"],
      fetch: answering(stream.response).fetch,
    });
    stream.push(throughReady);
    const names: string[] = [];
    for await (const event of events) {
      names.push(event.event);
      if (event.event === "ready") {
        break;
      }
    }
    expect(names).toMatchInlineSnapshot(`
      [
        "cell",
        "cell",
        "cell",
        "ready",
      ]
    `);
    expect(events.status).toBe("closed");
    await expect(events.closed).resolves.toBeUndefined();
  });

  it("follows a stream through a custom transport", async () => {
    vi.useFakeTimers();
    const attempts: (string | null)[] = [];
    const transport: NotebookTransport = async ({ cursor }, handlers) => {
      attempts.push(cursor);
      handlers.open();
      if (attempts.length === 1) {
        handlers.message({ event: "ready", id: "41", data: {} });
        return;
      }
      handlers.message({ event: "marimo", id: "42", data: { marimo: {} } });
      throw new StreamStopped("Shutting down", { cause: "MARIMO_SHUTDOWN" });
    };
    const events = new NotebookEvents(transport, { types: ["marimo"] });
    const received = collect(events);
    await vi.advanceTimersByTimeAsync(2000);
    const error = await events.closed.catch((error: unknown) => error);
    expect(attempts).toMatchInlineSnapshot(`
      [
        null,
        "41",
      ]
    `);
    expect(received.map((event) => event.event)).toMatchInlineSnapshot(`
      [
        "ready",
        "marimo",
      ]
    `);
    expect((error as StreamStopped).cause).toBe("MARIMO_SHUTDOWN");
  });

  it("stays closed when a transport opens after the stream closed", async () => {
    let open: (() => void) | undefined;
    const transport: NotebookTransport = (_attempt, handlers) => {
      open = handlers.open;
      return new Promise(() => undefined);
    };
    const events = new NotebookEvents(transport);
    await vi.waitFor(() => expect(open).toBeDefined());
    events.close();
    open?.();
    expect(events.status).toBe("closed");
  });

  it("wakes each pending read when events arrive", async () => {
    let message: ((message: unknown) => void) | undefined;
    const transport: NotebookTransport = (_attempt, handlers) => {
      message = handlers.message;
      return new Promise(() => undefined);
    };
    const events = new NotebookEvents(transport, { types: ["marimo"] });
    const iterator = events[Symbol.asyncIterator]();
    const first = iterator.next();
    const second = iterator.next();
    await vi.waitFor(() => expect(message).toBeDefined());
    message?.({ event: "marimo", id: "1", data: {} });
    message?.({ event: "marimo", id: "2", data: {} });
    expect((await first).value).toMatchObject({ id: "1" });
    expect((await second).value).toMatchObject({ id: "2" });
    await iterator.return?.();
    expect(events.status).toBe("closed");
  });

  it("stops a custom transport that delivers an invalid message", async () => {
    let signal: AbortSignal | undefined;
    const transport: NotebookTransport = (attempt, handlers) =>
      new Promise(() => {
        signal = attempt.signal;
        // A transport reports messages from its own listeners.
        queueMicrotask(() => handlers.message(null));
      });
    const events = new NotebookEvents(transport);
    const error = await events.closed.catch((error: unknown) => error);
    expect((error as StreamStopped).message).toContain("not an event");
    expect((error as StreamStopped).cause).toBeInstanceOf(z.ZodError);
    expect(signal?.aborted).toBe(true);
  });
});

describe("sse", () => {
  it("decodes raw data before stop and delivery, retaining text on parse errors", async () => {
    const stream = body();
    const message = vi.fn();
    const stop = vi.fn(() => undefined);
    const transport = sse(url, {
      fetch: answering(stream.response).fetch,
      parseData: (text) =>
        JSON.parse(text, (_key, value) =>
          typeof value === "number" ? BigInt(value) : value,
        ),
      stop,
    });
    stream.push('event: marimo\ndata: {"marimo":\ndata: {"value":42}}\n\n');
    stream.push("event: custom\ndata: plain text\n\n");
    stream.end();
    await transport(
      { cursor: null, signal: new AbortController().signal },
      { open: vi.fn(), message },
    );
    const frames = [
      { event: "marimo", data: { marimo: { value: 42n } } },
      { event: "custom", data: "plain text" },
    ];
    expect(stop.mock.calls).toEqual(frames.map((frame) => [frame]));
    expect(message.mock.calls).toEqual(frames.map((frame) => [frame]));
  });

  it("reads a URL given as a function before each connection", async () => {
    vi.useFakeTimers();
    const first = body();
    const { fetch, sent } = answering(first.response);
    let session = 1;
    const events = new NotebookEvents(
      sse(async () => `${url}?session_id=${session}`, { fetch }),
    );
    first.push(throughReady);
    await vi.waitFor(() => expect(events.cursor).toBe("95"));
    session = 2;
    first.end();
    await vi.advanceTimersByTimeAsync(2000);
    expect([sent(0).url, sent(1).url]).toMatchInlineSnapshot(`
      [
        "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1/events?session_id=1",
        "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1/events?session_id=2",
      ]
    `);
    expect(sent(1).headers.get("Last-Event-ID")).toBe("95");
    events.close();
  });

  it("stops on a frame outside the protocol when asked to", async () => {
    const stream = body();
    const shutdown = new Error("MARIMO_SHUTDOWN");
    const events = new NotebookEvents(
      sse(url, {
        fetch: answering(stream.response).fetch,
        stop: (frame) => (frame.event === "close" ? shutdown : undefined),
      }),
      { types: ["marimo"] },
    );
    const received = collect(events);
    stream.push('id: 1\nevent: marimo\ndata: {"marimo":{}}\n\n');
    stream.push(
      'event: close\ndata: {"code":1000,"reason":"MARIMO_SHUTDOWN"}\n\n',
    );
    await expect(events.closed).rejects.toBe(shutdown);
    expect(received.map((event) => event.event)).toEqual(["marimo"]);
  });
});

describe("NotebookClient.events", () => {
  it("follows the stream below the notebook's URL with the client's connection", async () => {
    const { fetch, sent } = answering();
    const notebook = new NotebookClient(
      "http://localhost/api/marimo/v1/notebooks/n1?session_id=s1",
      { token: "secret", fetch },
    );
    const events = notebook.events({ types: ["cell"] });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(sent(0).url).toBe(
      "http://localhost/api/marimo/v1/notebooks/n1/events?session_id=s1&types=cell",
    );
    expect(sent(0).headers.get("Authorization")).toBe("Bearer secret");
    events.close();
  });
});
