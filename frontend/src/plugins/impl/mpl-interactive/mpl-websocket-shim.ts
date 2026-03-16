/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Fake WebSocket that routes messages through MarimoComm / MODEL_MANAGER
 * instead of a real network WebSocket.
 *
 * mpl.js expects a WebSocket-like object with:
 *   - readyState
 *   - send(data: string)
 *   - onopen / onmessage / onclose callbacks
 */
export class MplCommWebSocket {
  readyState: number = WebSocket.OPEN;
  private sendFn: (msg: unknown) => void;

  onopen: (() => void) | null = null;
  onmessage: ((evt: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(sendFn: (msg: unknown) => void) {
    this.sendFn = sendFn;
  }

  /**
   * Called by mpl.js to send a message to the backend.
   * mpl.js always sends JSON strings.
   */
  send(data: string): void {
    this.sendFn(JSON.parse(data));
  }

  /**
   * Called when the backend pushes a JSON message via the model custom event.
   */
  receiveJson(data: unknown): void {
    this.onmessage?.(
      new MessageEvent("message", { data: JSON.stringify(data) }),
    );
  }

  /**
   * Called when the backend pushes binary data (PNG render) via model custom event.
   */
  receiveBinary(buffer: DataView): void {
    const ab = buffer.buffer.slice(
      buffer.byteOffset,
      buffer.byteOffset + buffer.byteLength,
    ) as ArrayBuffer;
    const blob = new Blob([ab]);
    this.onmessage?.(new MessageEvent("message", { data: blob }));
  }

  close(): void {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.();
  }
}
