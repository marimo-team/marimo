/* Copyright 2026 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import {
  type ConnectionEvent,
  ConnectionSubscriptions,
  type ConnectionTransportCallback,
  type IConnectionTransport,
} from "./transport";
import { MAX_RETRIES, TRANSPORT_EXHAUSTED_REASON } from "./ws";

// Mirrors WsTransport/partysocket retry behavior.
const CONNECTION_TIMEOUT_MS = 10_000;
const MIN_RETRY_DELAY_MS = 1000;
const MAX_RETRY_DELAY_MS = 10_000;
const RETRY_GROWTH_FACTOR = 1.3;

// Stream ended without a server close event (transient disconnect); matches
// the WebSocket abnormal-closure code so close handling stays uniform.
const ABNORMAL_CLOSURE = 1006;

interface ServerClose {
  code: number;
  reason: string;
}

/**
 * A kernel-connection transport over server-sent events, used when
 * `server.transport` is `"sse"` (experimental).
 *
 * The kernel connection only carries messages server to client (control
 * requests go over HTTP POST), so an SSE stream can fully replace the
 * WebSocket. The server mirrors WebSocket close frames with a `close` SSE
 * event carrying `{code, reason}`; a stream that ends without one is a
 * transient disconnect.
 *
 * Uses `fetch` + stream parsing rather than `EventSource`: we need to
 * surface server close reasons, send auth headers, and match partysocket's
 * retry semantics (per-`reconnect()` retry budget, exhaustion surfaced via
 * `TRANSPORT_EXHAUSTED_REASON`), none of which `EventSource` supports.
 *
 * Like `WsTransport`, starts closed; the first `reconnect()` connects.
 * `close()` stops retrying and does not dispatch a close event.
 */
export class SseTransport implements IConnectionTransport {
  private subscriptions = new ConnectionSubscriptions();
  private urlProvider: () => string;
  private headersProvider: () => Record<string, string>;
  private abortController: AbortController | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private retryCount = 0;
  private userClosed = false;
  private state: WebSocket["readyState"] = WebSocket.CLOSED;

  constructor(
    urlProvider: () => string,
    headersProvider: () => Record<string, string> = () => ({}),
  ) {
    this.urlProvider = urlProvider;
    this.headersProvider = headersProvider;
  }

  get readyState(): WebSocket["readyState"] {
    return this.state;
  }

  reconnect(_code?: number, _reason?: string): void {
    this.userClosed = false;
    this.retryCount = 0;
    this.clearRetryTimer();
    this.abortController?.abort();
    this.connect();
  }

  close(): void {
    this.userClosed = true;
    this.clearRetryTimer();
    this.state = WebSocket.CLOSED;
    this.abortController?.abort();
    this.abortController = null;
  }

  send(_data: string | ArrayBuffer | Blob | ArrayBufferView): void {
    // The kernel connection is receive-only; all client requests go over
    // HTTP POST endpoints.
    Logger.warn("SseTransport does not support send(); dropping message");
  }

  addEventListener<T extends ConnectionEvent>(
    event: T,
    callback: ConnectionTransportCallback<T>,
  ): void {
    this.subscriptions.addSubscription(
      event,
      callback as ConnectionTransportCallback<ConnectionEvent>,
    );
  }

  removeEventListener<T extends ConnectionEvent>(
    event: T,
    callback: ConnectionTransportCallback<T>,
  ): void {
    this.subscriptions.removeSubscription(
      event,
      callback as ConnectionTransportCallback<ConnectionEvent>,
    );
  }

  private connect(): void {
    this.state = WebSocket.CONNECTING;
    void this.run();
  }

  private async run(): Promise<void> {
    const controller = new AbortController();
    this.abortController = controller;
    // Long timeout — the server can become slow when many notebooks are open.
    const connectTimeout = setTimeout(
      () => controller.abort(),
      CONNECTION_TIMEOUT_MS,
    );

    let serverClose: ServerClose | null = null;
    try {
      const response = await fetch(this.urlProvider(), {
        headers: {
          ...this.headersProvider(),
          Accept: "text/event-stream",
        },
        signal: controller.signal,
      });
      clearTimeout(connectTimeout);
      if (!response.ok || response.body === null) {
        throw new Error(`Unexpected SSE response: ${response.status}`);
      }

      this.state = WebSocket.OPEN;
      this.subscriptions.notify("open", new Event("open"));

      serverClose = await this.readEvents(response.body);
    } catch (error) {
      clearTimeout(connectTimeout);
      if (this.isSuperseded(controller)) {
        return;
      }
      Logger.warn("SSE connection failed", error);
      this.subscriptions.notify("error", new Event("error"));
    }

    if (this.isSuperseded(controller)) {
      return;
    }
    controller.abort();
    this.state = WebSocket.CLOSED;

    // The retry budget counts consecutive attempts without a healthy
    // stream (readEvents resets it on the first message), so a server
    // that accepts and immediately closes still exhausts the budget.
    this.retryCount += 1;
    const exhausted = this.retryCount >= MAX_RETRIES;
    this.subscriptions.notify(
      "close",
      new CloseEvent("close", {
        code: serverClose?.code ?? ABNORMAL_CLOSURE,
        // On exhaustion the reason is rewritten so the consumer stops
        // retrying, matching WsTransport.
        reason: exhausted
          ? TRANSPORT_EXHAUSTED_REASON
          : (serverClose?.reason ?? ""),
        wasClean: serverClose !== null,
      }),
    );
    // The consumer's close handler runs synchronously inside notify and
    // may have called reconnect() (starting a fresh connection) or
    // close(); re-check before scheduling our own retry so we never
    // stack a second connection on top of theirs.
    if (exhausted || this.isSuperseded(controller)) {
      return;
    }
    this.scheduleRetry();
  }

  /** Whether this run was replaced by a newer reconnect() or close(). */
  private isSuperseded(controller: AbortController): boolean {
    return this.userClosed || this.abortController !== controller;
  }

  private scheduleRetry(): void {
    this.clearRetryTimer();
    this.state = WebSocket.CONNECTING;
    const delay = Math.min(
      MIN_RETRY_DELAY_MS * RETRY_GROWTH_FACTOR ** this.retryCount,
      MAX_RETRY_DELAY_MS,
    );
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      this.connect();
    }, delay);
  }

  private clearRetryTimer(): void {
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
  }

  /**
   * Read and dispatch SSE events until the stream ends.
   *
   * Returns the server close payload if a `close` event arrives, or null
   * if the stream ends without one.
   */
  private async readEvents(
    body: ReadableStream<Uint8Array>,
  ): Promise<ServerClose | null> {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let eventName: string | null = null;
    let dataLines: string[] = [];

    const dispatch = (): ServerClose | null => {
      if (dataLines.length === 0) {
        eventName = null;
        return null;
      }
      const data = dataLines.join("\n");
      const name = eventName;
      eventName = null;
      dataLines = [];
      if (name === "close") {
        return parseServerClose(data);
      }
      // A message means the stream is healthy: reset the retry budget
      // (rather than on open, so a server that accepts and immediately
      // closes cannot retry forever).
      this.retryCount = 0;
      this.subscriptions.notify(
        "message",
        new MessageEvent("message", { data }),
      );
      return null;
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        return null;
      }
      buffer += decoder.decode(value, { stream: true });

      // Consume complete lines with a cursor; a single tail slice per
      // read keeps parsing linear even for many buffered lines.
      let cursor = 0;
      let newlineIndex = buffer.indexOf("\n", cursor);
      while (newlineIndex !== -1) {
        let line = buffer.slice(cursor, newlineIndex);
        cursor = newlineIndex + 1;
        newlineIndex = buffer.indexOf("\n", cursor);
        if (line.endsWith("\r")) {
          line = line.slice(0, -1);
        }

        if (line === "") {
          const serverClose = dispatch();
          if (serverClose !== null) {
            return serverClose;
          }
          continue;
        }
        if (line.startsWith(":")) {
          // Comment (keep-alive)
          continue;
        }

        const colonIndex = line.indexOf(":");
        const field = colonIndex === -1 ? line : line.slice(0, colonIndex);
        let fieldValue = colonIndex === -1 ? "" : line.slice(colonIndex + 1);
        if (fieldValue.startsWith(" ")) {
          fieldValue = fieldValue.slice(1);
        }
        if (field === "data") {
          dataLines.push(fieldValue);
        } else if (field === "event") {
          eventName = fieldValue;
        }
        // `id` and `retry` fields are unused.
      }
      if (cursor > 0) {
        buffer = buffer.slice(cursor);
      }
    }
  }
}

function parseServerClose(data: string): ServerClose {
  try {
    const parsed = JSON.parse(data) as Partial<ServerClose>;
    return {
      code: typeof parsed.code === "number" ? parsed.code : 1000,
      reason: typeof parsed.reason === "string" ? parsed.reason : "",
    };
  } catch {
    Logger.warn("Failed to parse SSE close event", data);
    return { code: 1000, reason: "" };
  }
}
