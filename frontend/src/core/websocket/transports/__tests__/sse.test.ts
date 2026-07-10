/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SseTransport } from "../sse";
import { MAX_RETRIES, TRANSPORT_EXHAUSTED_REASON } from "../ws";

const encoder = new TextEncoder();

function createControllableStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  return {
    stream,
    push: (text: string) => controller.enqueue(encoder.encode(text)),
    end: () => controller.close(),
  };
}

function sseResponse(body: ReadableStream<Uint8Array> | null, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    body,
  } as Response;
}

describe("SseTransport", () => {
  let transport: SseTransport;
  let fetchMock: ReturnType<typeof vi.fn>;
  let opens: Event[];
  let messages: MessageEvent[];
  let closes: CloseEvent[];
  let errors: Event[];

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    transport = new SseTransport(() => "http://example.invalid/sse");
    opens = [];
    messages = [];
    closes = [];
    errors = [];
    transport.addEventListener("open", (e) => opens.push(e));
    transport.addEventListener("message", (e) => messages.push(e));
    transport.addEventListener("close", (e) => closes.push(e));
    transport.addEventListener("error", (e) => errors.push(e));
  });

  afterEach(() => {
    transport.close();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("starts closed and connects on reconnect()", async () => {
    expect(transport.readyState).toBe(WebSocket.CLOSED);
    const { stream } = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(stream));

    transport.reconnect();
    expect(transport.readyState).toBe(WebSocket.CONNECTING);
    await vi.waitFor(() => expect(opens).toHaveLength(1));
    expect(transport.readyState).toBe(WebSocket.OPEN);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://example.invalid/sse",
      expect.objectContaining({
        headers: { Accept: "text/event-stream" },
      }),
    );
  });

  it("dispatches message events, joining multi-line data", async () => {
    const { stream, push } = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(stream));
    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(1));

    push('data: {"op": "alert"}\n\n');
    await vi.waitFor(() => expect(messages).toHaveLength(1));
    expect(messages[0].data).toBe('{"op": "alert"}');

    // Multi-line data and records split across chunks
    push("data: line1\nda");
    push("ta: line2\n\n");
    await vi.waitFor(() => expect(messages).toHaveLength(2));
    expect(messages[1].data).toBe("line1\nline2");
  });

  it("ignores keep-alive comments", async () => {
    const { stream, push } = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(stream));
    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(1));

    push(": keep-alive\n\n");
    push("data: after\n\n");
    await vi.waitFor(() => expect(messages).toHaveLength(1));
    expect(messages[0].data).toBe("after");
  });

  it("surfaces a server close event with its code and reason", async () => {
    const { stream, push } = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(stream));
    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(1));

    // Stop retrying when the consumer treats the close as terminal,
    // mirroring useMarimoKernelConnection's terminal path.
    transport.addEventListener("close", () => transport.close());
    push('event: close\ndata: {"code": 1000, "reason": "MARIMO_SHUTDOWN"}\n\n');
    await vi.waitFor(() => expect(closes).toHaveLength(1));
    expect(closes[0].code).toBe(1000);
    expect(closes[0].reason).toBe("MARIMO_SHUTDOWN");
    expect(closes[0].wasClean).toBe(true);
    expect(transport.readyState).toBe(WebSocket.CLOSED);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("emits an empty-reason close and retries when the stream ends", async () => {
    vi.useFakeTimers();
    const first = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(first.stream));
    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(1));

    first.end();
    await vi.waitFor(() => expect(closes).toHaveLength(1));
    expect(closes[0].reason).toBe("");
    expect(closes[0].wasClean).toBe(false);

    // A retry is scheduled and reconnects
    const second = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(second.stream));
    await vi.advanceTimersByTimeAsync(10_000);
    await vi.waitFor(() => expect(opens).toHaveLength(2));
  });

  it("does not stack its own retry when the consumer reconnects in onClose", async () => {
    vi.useFakeTimers();
    const first = createControllableStream();
    const second = createControllableStream();
    fetchMock
      .mockResolvedValueOnce(sseResponse(first.stream))
      .mockResolvedValueOnce(sseResponse(second.stream));
    // Mirror useMarimoKernelConnection's retry path: reconnect()
    // synchronously from inside the close handler.
    transport.addEventListener("close", () => transport.reconnect());

    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(1));

    first.end();
    await vi.waitFor(() => expect(opens).toHaveLength(2));

    // The superseded run must not schedule a second connection on top of
    // the consumer's reconnect.
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // The consumer-driven connection is healthy
    second.push("data: alive\n\n");
    await vi.waitFor(() => expect(messages).toHaveLength(1));
    expect(transport.readyState).toBe(WebSocket.OPEN);
  });

  it("exhausts the retry budget when the server closes every connection", async () => {
    vi.useFakeTimers();
    // A server that accepts, immediately sends a close event, and never
    // delivers a message must not be retried forever.
    fetchMock.mockImplementation(() => {
      const { stream, push } = createControllableStream();
      push('event: close\ndata: {"code": 3000, "reason": "MARIMO_X"}\n\n');
      return Promise.resolve(sseResponse(stream));
    });

    transport.reconnect();
    for (let i = 0; i < MAX_RETRIES; i++) {
      await vi.advanceTimersByTimeAsync(15_000);
    }

    expect(closes.length).toBe(MAX_RETRIES);
    expect(closes.at(-1)?.reason).toBe(TRANSPORT_EXHAUSTED_REASON);
    const fetchCallsWhenExhausted = fetchMock.mock.calls.length;
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchMock.mock.calls.length).toBe(fetchCallsWhenExhausted);
  });

  it("a delivered message resets the retry budget", async () => {
    vi.useFakeTimers();
    const first = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(first.stream));
    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(1));
    first.push("data: healthy\n\n");
    await vi.waitFor(() => expect(messages).toHaveLength(1));

    first.end();
    await vi.waitFor(() => expect(closes).toHaveLength(1));
    // Budget was reset by the message, so this close is retry #1, not
    // an exhaustion.
    expect(closes[0].reason).toBe("");
  });

  it("gives up with TRANSPORT_EXHAUSTED_REASON after MAX_RETRIES failures", async () => {
    vi.useFakeTimers();
    fetchMock.mockRejectedValue(new Error("connection refused"));

    transport.reconnect();
    for (let i = 0; i < MAX_RETRIES; i++) {
      await vi.advanceTimersByTimeAsync(15_000);
    }

    expect(closes.length).toBe(MAX_RETRIES);
    expect(closes.at(-1)?.reason).toBe(TRANSPORT_EXHAUSTED_REASON);
    expect(errors.length).toBe(MAX_RETRIES);
    const fetchCallsWhenExhausted = fetchMock.mock.calls.length;

    // No further retries once exhausted
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchMock.mock.calls.length).toBe(fetchCallsWhenExhausted);

    // A manual reconnect() resets the budget
    const { stream } = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(stream));
    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(1));
  });

  it("close() aborts the connection and cancels retries", async () => {
    vi.useFakeTimers();
    const { stream } = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(stream));
    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(1));

    transport.close();
    expect(transport.readyState).toBe(WebSocket.CLOSED);
    // No close event is dispatched for a user-initiated close, and no
    // retry is scheduled.
    await vi.advanceTimersByTimeAsync(60_000);
    expect(closes).toHaveLength(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("treats a non-2xx response as a connection failure", async () => {
    vi.useFakeTimers();
    fetchMock.mockResolvedValueOnce(sseResponse(null, 500));
    transport.reconnect();

    await vi.waitFor(() => expect(closes).toHaveLength(1));
    expect(opens).toHaveLength(0);
    expect(errors).toHaveLength(1);
    expect(closes[0].reason).toBe("");
  });

  it("sends provided headers (auth) with the request", async () => {
    const withHeaders = new SseTransport(
      () => "http://example.invalid/sse",
      () => ({ Authorization: "Bearer token123" }),
    );
    const { stream } = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(stream));
    withHeaders.reconnect();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    withHeaders.close();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://example.invalid/sse",
      expect.objectContaining({
        headers: {
          Authorization: "Bearer token123",
          Accept: "text/event-stream",
        },
      }),
    );
  });

  it("aborts a connection attempt that exceeds the timeout", async () => {
    vi.useFakeTimers();
    // fetch that only settles when aborted
    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new Error("aborted")),
          );
        }),
    );

    transport.reconnect();
    await vi.advanceTimersByTimeAsync(11_000);
    expect(errors).toHaveLength(1);
    expect(closes).toHaveLength(1);
    expect(closes[0].reason).toBe("");
  });

  it("reconnect() mid-stream supersedes the old connection silently", async () => {
    const first = createControllableStream();
    const second = createControllableStream();
    fetchMock
      .mockResolvedValueOnce(sseResponse(first.stream))
      .mockResolvedValueOnce(sseResponse(second.stream));

    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(1));

    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(2));

    // The aborted first connection must not surface close/error events
    second.push("data: alive\n\n");
    await vi.waitFor(() => expect(messages).toHaveLength(1));
    expect(closes).toHaveLength(0);
    expect(errors).toHaveLength(0);
  });

  it("send() is a no-op", () => {
    expect(() => transport.send("data")).not.toThrow();
  });

  it("dedupes repeated addEventListener calls", async () => {
    const { stream, push } = createControllableStream();
    fetchMock.mockResolvedValueOnce(sseResponse(stream));
    const onMessage = (e: MessageEvent) => messages.push(e);
    transport.addEventListener("message", onMessage);
    transport.addEventListener("message", onMessage);
    transport.reconnect();
    await vi.waitFor(() => expect(opens).toHaveLength(1));

    push("data: once\n\n");
    // The beforeEach listener plus the deduped listener = 2 events
    await vi.waitFor(() => expect(messages).toHaveLength(2));
  });
});
