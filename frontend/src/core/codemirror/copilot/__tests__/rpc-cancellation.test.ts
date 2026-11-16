/* Copyright 2026 Marimo. All rights reserved. */

import {
  JSONRPCClient,
  type JSONRPCMessage,
  type Transport,
} from "@marimo-team/codemirror-languageserver";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("LSP request cancellation", () => {
  let client: JSONRPCClient;
  let emit: (message: JSONRPCMessage) => void;
  let disconnect: (error: Error) => void;
  let connected: ReturnType<typeof Promise.withResolvers<undefined>>;
  let transport: Transport & {
    send: ReturnType<typeof vi.fn<(message: JSONRPCMessage) => void>>;
  };

  beforeEach(() => {
    vi.useFakeTimers();
    connected = Promise.withResolvers<undefined>();
    transport = {
      connect: () => connected.promise,
      close: vi.fn(),
      send: vi.fn<(message: JSONRPCMessage) => void>(),
      onMessage: (handler) => {
        emit = handler;
        return vi.fn();
      },
      onClose: (handler) => {
        disconnect = handler;
        return vi.fn();
      },
    };
    client = new JSONRPCClient(transport);
  });

  afterEach(() => {
    client.close();
    vi.useRealTimers();
  });

  async function connect() {
    connected.resolve(undefined);
    await vi.advanceTimersByTimeAsync(0);
  }

  it("does not send an already-aborted request", async () => {
    await connect();
    const controller = new AbortController();
    controller.abort();
    await expect(
      client.request("complete", {}, 1000, controller.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(transport.send).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("cancels while connecting without sending either request or cancellation", async () => {
    const controller = new AbortController();
    const response = client.request("complete", {}, 1000, controller.signal);
    controller.abort();
    await expect(response).rejects.toMatchObject({ name: "AbortError" });
    await connect();
    expect(transport.send).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("rejects a failed connection and removes the waiting request's abort listener", async () => {
    const controller = new AbortController();
    const remove = vi.spyOn(controller.signal, "removeEventListener");
    const response = client.request("complete", {}, 1000, controller.signal);
    const settled = response.catch((error: unknown) => error);
    connected.reject(new Error("connection refused"));
    await expect(settled).resolves.toMatchObject({
      message: "connection refused",
    });
    expect(remove).toHaveBeenCalledExactlyOnceWith(
      "abort",
      expect.any(Function),
    );
    controller.abort();
    expect(transport.send).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("cancels exactly the matching request, ignores late replies, and leaves others active", async () => {
    await connect();
    const controller = new AbortController();
    const first = client.request(
      "complete",
      { position: 1 },
      1000,
      controller.signal,
    );
    const second = client.request("complete", { position: 2 }, 1000);
    controller.abort();
    controller.abort();
    await expect(first).rejects.toMatchObject({ name: "AbortError" });
    emit({ jsonrpc: "2.0", id: 0, result: "stale" });
    emit({ jsonrpc: "2.0", id: 1, result: "latest" });
    await expect(second).resolves.toBe("latest");
    expect(transport.send.mock.calls).toEqual([
      [{ jsonrpc: "2.0", id: 0, method: "complete", params: { position: 1 } }],
      [{ jsonrpc: "2.0", id: 1, method: "complete", params: { position: 2 } }],
      [{ jsonrpc: "2.0", method: "$/cancelRequest", params: { id: 0 } }],
    ]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each([
    "success",
    "error",
    "timeout",
    "disconnect",
    "close",
    "send failure",
  ])("removes the abort listener and timer after %s", async (outcome) => {
    await connect();
    const controller = new AbortController();
    const remove = vi.spyOn(controller.signal, "removeEventListener");
    if (outcome === "send failure") {
      transport.send.mockImplementationOnce(() => {
        throw new Error("send failed");
      });
    }
    const response = client.request("complete", {}, 1000, controller.signal);
    // Attach the rejection handler before advancing timers or dropping the connection.
    const settled = response.then(
      (value) => ({ status: "fulfilled", value }),
      (error: unknown) => ({ status: "rejected", error }),
    );
    if (outcome === "success") {
      emit({ jsonrpc: "2.0", id: 0, result: "ok" });
    }
    if (outcome === "error") {
      emit({
        jsonrpc: "2.0",
        id: 0,
        error: { code: -32603, message: "failed" },
      });
    }
    if (outcome === "timeout") {
      await vi.advanceTimersByTimeAsync(1000);
    }
    if (outcome === "disconnect") {
      disconnect(new Error("disconnected"));
    }
    if (outcome === "close") {
      client.close();
    }
    const expectedError = expect.any(Error);
    expect(await settled).toEqual(
      outcome === "success"
        ? { status: "fulfilled", value: "ok" }
        : { status: "rejected", error: expectedError },
    );
    expect(remove).toHaveBeenCalledExactlyOnceWith(
      "abort",
      expect.any(Function),
    );
    expect(vi.getTimerCount()).toBe(0);
    const calls = transport.send.mock.calls.length;
    controller.abort();
    expect(transport.send).toHaveBeenCalledTimes(calls);
  });

  it("sends exactly one cancellation at the timeout boundary and ignores a late reply", async () => {
    await connect();
    const controller = new AbortController();
    const settled = client
      .request("complete", {}, 1000, controller.signal)
      .catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(999);
    expect(transport.send.mock.calls).toEqual([
      [{ jsonrpc: "2.0", id: 0, method: "complete", params: {} }],
    ]);
    await vi.advanceTimersByTimeAsync(1);
    expect(transport.send.mock.calls).toEqual([
      [{ jsonrpc: "2.0", id: 0, method: "complete", params: {} }],
      [{ jsonrpc: "2.0", method: "$/cancelRequest", params: { id: 0 } }],
    ]);
    emit({ jsonrpc: "2.0", id: 0, result: "late" });
    controller.abort();
    await expect(settled).resolves.toMatchObject({ code: -32001 });
    expect(transport.send).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("settles cancellation even if sending the cancellation notification fails", async () => {
    await connect();
    const controller = new AbortController();
    const response = client.request("complete", {}, 1000, controller.signal);
    transport.send.mockImplementationOnce(() => {
      throw new Error("connection gone");
    });
    controller.abort();
    await expect(response).rejects.toMatchObject({ name: "AbortError" });
    expect(vi.getTimerCount()).toBe(0);
  });
});
