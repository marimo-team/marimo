/* Copyright 2026 Marimo. All rights reserved. */

import ReconnectingWebSocket from "partysocket/ws";
import type {
  ConnectionEvent,
  ConnectionTransportCallback,
  IConnectionTransport,
} from "./transport";

// Per-`reconnect()` retry budget. After exhaustion, partysocket stops silently;
// the wrapper rewrites the close-event reason to surface the give-up.
export const MAX_RETRIES = 10;

export const TRANSPORT_EXHAUSTED_REASON = "MARIMO_TRANSPORT_EXHAUSTED";

export class PartysocketTransport implements IConnectionTransport {
  private inner: ReconnectingWebSocket;
  private closeWrappers = new WeakMap<
    ConnectionTransportCallback<"close">,
    ConnectionTransportCallback<"close">
  >();

  constructor(urlProvider: () => string) {
    this.inner = new ReconnectingWebSocket(urlProvider, undefined, {
      maxRetries: MAX_RETRIES,
      debug: false,
      startClosed: true,
      // long timeout — the server can become slow when many notebooks are open.
      connectionTimeout: 10_000,
    });
  }

  get readyState(): WebSocket["readyState"] {
    return this.inner.readyState as WebSocket["readyState"];
  }

  reconnect(code?: number, reason?: string): void {
    this.inner.reconnect(code, reason);
  }

  close(): void {
    this.inner.close();
  }

  send(data: string | ArrayBuffer | Blob | ArrayBufferView): void {
    this.inner.send(data);
  }

  addEventListener<T extends ConnectionEvent>(
    event: T,
    callback: ConnectionTransportCallback<T>,
  ): void {
    if (event === "close") {
      const userCb = callback as ConnectionTransportCallback<"close">;
      const wrapper: ConnectionTransportCallback<"close"> = (e) => {
        if (this.inner.retryCount >= MAX_RETRIES) {
          userCb(
            new CloseEvent("close", {
              code: e.code,
              reason: TRANSPORT_EXHAUSTED_REASON,
              wasClean: e.wasClean,
            }),
          );
        } else {
          userCb(e);
        }
      };
      this.closeWrappers.set(userCb, wrapper);
      this.inner.addEventListener("close", wrapper);
      return;
    }
    this.inner.addEventListener(event, callback as never);
  }

  removeEventListener<T extends ConnectionEvent>(
    event: T,
    callback: ConnectionTransportCallback<T>,
  ): void {
    if (event === "close") {
      const userCb = callback as ConnectionTransportCallback<"close">;
      const wrapper = this.closeWrappers.get(userCb);
      if (wrapper) {
        this.closeWrappers.delete(userCb);
        this.inner.removeEventListener("close", wrapper);
      }
      return;
    }
    this.inner.removeEventListener(event, callback as never);
  }
}
