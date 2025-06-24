/* Copyright 2024 Marimo. All rights reserved. */
import type { IReconnectingWebSocket } from "./types";
import type { isIslands } from "@core/islands/utils";

export class StaticWebsocket implements IReconnectingWebSocket {
  CONNECTING = WebSocket.CONNECTING;
  OPEN = WebSocket.OPEN;
  CLOSING = WebSocket.CLOSING;
  CLOSED = WebSocket.CLOSED;
  binaryType = "blob" as BinaryType;
  bufferedAmount = 0;
  extensions = "";
  protocol = "";
  url = "";

  onclose = null;
  onerror = null;
  onmessage = null;
  onopen = null;

  addEventListener(
    type: string,
    callback: EventListener,
    _options?: unknown,
  ): void {
    // Normally this would be a no-op in a mock, but we simulate a synthetic "open" event
    // to mimic the WebSocket transitioning from CONNECTING to OPEN state.
    if (type === "open" && !isIslands()) {
      queueMicrotask(() => {
        callback(new Event("open"));
      });
    }
  }

  removeEventListener(
    type: unknown,
    callback: unknown,
    options?: unknown,
  ): void {
    // Noop
  }
  dispatchEvent(event: Event): boolean {
    // Noop
    return false;
  }

  readyState = WebSocket.OPEN;
  retryCount = 0;
  shouldReconnect = false;

  reconnect(code?: number | undefined, reason?: string | undefined): void {
    // Noop
  }
  send(data: string | ArrayBuffer | Blob | ArrayBufferView) {
    // Noop
  }
  close() {
    // Noop
  }
}
