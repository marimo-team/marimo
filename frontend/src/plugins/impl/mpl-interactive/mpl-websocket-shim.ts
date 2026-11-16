/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Fake WebSocket that routes messages through MarimoComm / WIDGET_REGISTRY
 * instead of a real network WebSocket.
 *
 * mpl.js expects a WebSocket-like object with:
 *   - readyState
 *   - send(data: string)
 *   - onopen / onmessage / onclose callbacks
 */
export class MplCommWebSocket {
  public readyState: number = WebSocket.OPEN;
  private sendFn: (msg: unknown) => void;

  public onopen: (() => void) | null = null;
  public onmessage: ((evt: MessageEvent) => void) | null = null;
  public onclose: (() => void) | null = null;

  public constructor(sendFn: (msg: unknown) => void) {
    this.sendFn = sendFn;
  }

  /**
   * Re-point outbound sends at a new backend comm without recreating the
   * socket. The figure manager is reused across cell reruns, so the same
   * socket instance stays bound to mpl.js (which wires `onopen`/`onmessage`
   * onto it at construction); only the comm behind it changes.
   */
  public setSendHandler(sendFn: (msg: unknown) => void): void {
    this.sendFn = sendFn;
  }

  /**
   * Called by mpl.js to send a message to the backend.
   * mpl.js always sends JSON strings.
   */
  public send(data: string): void {
    this.sendFn(JSON.parse(data));
  }

  /**
   * Called when the backend pushes a JSON message via the model custom event.
   */
  public receiveJson(data: unknown): void {
    this.onmessage?.(
      new MessageEvent("message", { data: JSON.stringify(data) }),
    );
  }

  /**
   * Called when the backend pushes binary data (PNG render) via model custom event.
   */
  public receiveBinary(buffer: DataView): void {
    const ab = buffer.buffer.slice(
      buffer.byteOffset,
      buffer.byteOffset + buffer.byteLength,
    ) as ArrayBuffer;
    const blob = new Blob([ab]);
    this.onmessage?.(new MessageEvent("message", { data: blob }));
  }

  public close(): void {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.();
  }
}
