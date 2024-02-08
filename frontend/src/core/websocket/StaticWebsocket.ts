/* Copyright 2024 Marimo. All rights reserved. */
import { IReconnectingWebSocket } from "./types";

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

  addEventListener(type: unknown, callback: unknown, options?: unknown): void {
    // Noop
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
  send(data: string | ArrayBufferLike | Blob | ArrayBufferView) {
    // Noop
  }
  close() {
    // Noop
  }
}
