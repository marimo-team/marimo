/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { MplCommWebSocket } from "../mpl-websocket-shim";

describe("MplCommWebSocket", () => {
  it("starts in OPEN state", () => {
    const ws = new MplCommWebSocket(vi.fn());
    expect(ws.readyState).toBe(WebSocket.OPEN);
  });

  it("send() parses JSON and calls sendFn with parsed object", () => {
    const sendFn = vi.fn();
    const ws = new MplCommWebSocket(sendFn);

    ws.send(JSON.stringify({ type: "resize", width: 640, height: 480 }));

    expect(sendFn).toHaveBeenCalledOnce();
    expect(sendFn).toHaveBeenCalledWith({
      type: "resize",
      width: 640,
      height: 480,
    });
  });

  it("receiveJson() dispatches MessageEvent with JSON string data", () => {
    const ws = new MplCommWebSocket(vi.fn());
    const handler = vi.fn();
    ws.onmessage = handler;

    ws.receiveJson({ type: "figure_size", size: [640, 480] });

    expect(handler).toHaveBeenCalledOnce();
    const event: MessageEvent = handler.mock.calls[0][0];
    expect(event).toBeInstanceOf(MessageEvent);
    expect(event.type).toBe("message");
    expect(JSON.parse(event.data as string)).toEqual({
      type: "figure_size",
      size: [640, 480],
    });
  });

  it("receiveJson() is a no-op if onmessage is not set", () => {
    const ws = new MplCommWebSocket(vi.fn());
    // Should not throw
    ws.receiveJson({ type: "test" });
  });

  it("receiveBinary() dispatches MessageEvent with Blob data", () => {
    const ws = new MplCommWebSocket(vi.fn());
    const handler = vi.fn();
    ws.onmessage = handler;

    // Simulate a PNG-like binary buffer
    const bytes = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0, 1, 2, 3]);
    const dv = new DataView(bytes.buffer);

    ws.receiveBinary(dv);

    expect(handler).toHaveBeenCalledOnce();
    const event: MessageEvent = handler.mock.calls[0][0];
    expect(event).toBeInstanceOf(MessageEvent);
    expect(event.data).toBeInstanceOf(Blob);
    expect((event.data as Blob).size).toBe(8);
  });

  it("receiveBinary() handles DataView with offset", () => {
    const ws = new MplCommWebSocket(vi.fn());
    const handler = vi.fn();
    ws.onmessage = handler;

    // Create a DataView that's a slice of a larger buffer
    const fullBuffer = new ArrayBuffer(16);
    const fullView = new Uint8Array(fullBuffer);
    fullView.set([0, 0, 0, 0, 0x89, 0x50, 0x4e, 0x47, 0, 1, 2, 3, 0, 0, 0, 0]);
    const dv = new DataView(fullBuffer, 4, 8);

    ws.receiveBinary(dv);

    expect(handler).toHaveBeenCalledOnce();
    const blob = handler.mock.calls[0][0].data as Blob;
    expect(blob.size).toBe(8);
  });

  it("close() sets readyState to CLOSED and fires onclose", () => {
    const ws = new MplCommWebSocket(vi.fn());
    const closeHandler = vi.fn();
    ws.onclose = closeHandler;

    ws.close();

    expect(ws.readyState).toBe(WebSocket.CLOSED);
    expect(closeHandler).toHaveBeenCalledOnce();
  });

  it("close() does not throw if onclose is not set", () => {
    const ws = new MplCommWebSocket(vi.fn());
    ws.close();
    expect(ws.readyState).toBe(WebSocket.CLOSED);
  });

  it("onopen can be triggered externally", () => {
    const ws = new MplCommWebSocket(vi.fn());
    const openHandler = vi.fn();
    ws.onopen = openHandler;

    ws.onopen?.();

    expect(openHandler).toHaveBeenCalledOnce();
  });
});
