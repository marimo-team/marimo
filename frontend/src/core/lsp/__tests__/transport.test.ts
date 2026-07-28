/* Copyright 2026 Marimo. All rights reserved. */
import type { JSONRPCMessage } from "@marimo-team/codemirror-languageserver";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";
import { isRecord } from "@/utils/records";
import { ReconnectingWebSocketTransport } from "../transport";

vi.mock("@/utils/Logger", () => ({
  Logger: Mocks.logger(),
}));

class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static readonly instances: FakeWebSocket[] = [];

  readonly sent: string[] = [];
  readonly url: string;
  readonly protocols: string | string[] | undefined;
  readyState = FakeWebSocket.CONNECTING;
  private readonly listeners = new Map<
    string,
    Set<(event: { data?: unknown }) => void>
  >();

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = protocols;
    FakeWebSocket.instances.push(this);
  }

  addEventListener(
    type: string,
    listener: (event: { data?: unknown }) => void,
  ) {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  send(frame: string) {
    this.sent.push(frame);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
    this.emit("close", {});
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.emit("open", {});
  }

  fail() {
    this.emit("error", {});
  }

  disconnect() {
    this.readyState = FakeWebSocket.CLOSED;
    this.emit("close", {});
  }

  receive(message: JSONRPCMessage) {
    this.emit("message", { data: JSON.stringify(message) });
  }

  messages(): JSONRPCMessage[] {
    return this.sent.map((frame) => {
      const message: unknown = JSON.parse(frame);
      if (!isJSONRPCMessage(message)) {
        throw new Error("Fake WebSocket received an invalid JSON-RPC message");
      }
      return message;
    });
  }

  private emit(type: string, event: { data?: unknown }) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

function isJSONRPCMessage(value: unknown): value is JSONRPCMessage {
  if (!isRecord(value) || value.jsonrpc !== "2.0") {
    return false;
  }
  if (typeof value.method === "string") {
    return true;
  }
  return (
    (typeof value.id === "string" || typeof value.id === "number") &&
    ("result" in value || "error" in value)
  );
}

async function getSocket(index: number): Promise<FakeWebSocket> {
  await vi.waitFor(() => {
    expect(FakeWebSocket.instances.length).toBeGreaterThan(index);
  });
  return FakeWebSocket.instances[index];
}

describe("ReconnectingWebSocketTransport", () => {
  const mockWsUrl = "ws://localhost:8080/lsp";

  beforeEach(() => {
    FakeWebSocket.instances.length = 0;
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("waits for prerequisites and shares concurrent connection attempts", async () => {
    let releaseConnection: (() => void) | undefined;
    const waitForConnection = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          releaseConnection = resolve;
        }),
    );
    const getWsUrl = vi.fn(() => mockWsUrl);
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl,
      waitForConnection,
    });

    const firstConnection = transport.connect();
    const secondConnection = transport.connect();
    expect(waitForConnection).toHaveBeenCalledTimes(1);
    expect(FakeWebSocket.instances).toHaveLength(0);

    releaseConnection?.();
    const socket = await getSocket(0);
    socket.open();
    await Promise.all([firstConnection, secondConnection]);

    expect(socket.url).toBe(mockWsUrl);
    expect(getWsUrl).toHaveBeenCalledTimes(1);
  });

  it("forwards messages in both directions and supports unsubscribe", async () => {
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
    });
    const inbound = vi.fn();
    const unsubscribe = transport.onMessage(inbound);
    const connection = transport.connect();
    const socket = await getSocket(0);
    socket.open();
    await connection;

    const outbound: JSONRPCMessage = {
      jsonrpc: "2.0",
      method: "initialized",
      params: {},
    };
    transport.send(outbound);
    expect(socket.messages()).toEqual([outbound]);

    const notification: JSONRPCMessage = {
      jsonrpc: "2.0",
      method: "textDocument/publishDiagnostics",
      params: { uri: "file:///test.py", diagnostics: [] },
    };
    socket.receive(notification);
    expect(inbound).toHaveBeenCalledWith(notification);

    unsubscribe();
    socket.receive(notification);
    expect(inbound).toHaveBeenCalledTimes(1);
  });

  it("restores LSP state before replaying queued requests", async () => {
    const onReconnect = vi.fn(async () => {
      transport.send({
        jsonrpc: "2.0",
        method: "initialized",
        params: {},
      });
      transport.send({
        jsonrpc: "2.0",
        method: "textDocument/didOpen",
        params: { textDocument: { uri: "file:///test.py" } },
      });
    });
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
      onReconnect,
    });

    const initialConnection = transport.connect();
    const firstSocket = await getSocket(0);
    firstSocket.open();
    await initialConnection;
    firstSocket.disconnect();

    transport.send({
      jsonrpc: "2.0",
      method: "textDocument/didChange",
      params: { textDocument: { uri: "file:///test.py", version: 2 } },
    });
    const completionRequest: JSONRPCMessage = {
      jsonrpc: "2.0",
      id: 1,
      method: "textDocument/completion",
      params: { textDocument: { uri: "file:///test.py" } },
    };
    transport.send(completionRequest);

    const secondSocket = await getSocket(1);
    secondSocket.open();
    await vi.waitFor(() => {
      expect(onReconnect).toHaveBeenCalledTimes(1);
      expect(secondSocket.messages()).toHaveLength(3);
    });

    expect(secondSocket.messages()).toEqual([
      {
        jsonrpc: "2.0",
        method: "initialized",
        params: {},
      },
      {
        jsonrpc: "2.0",
        method: "textDocument/didOpen",
        params: { textDocument: { uri: "file:///test.py" } },
      },
      completionRequest,
    ]);
  });

  it("holds live requests until asynchronous state restoration finishes", async () => {
    let finishRestoration: (() => void) | undefined;
    const restorationGate = new Promise<void>((resolve) => {
      finishRestoration = resolve;
    });
    const onReconnect = vi.fn(async () => {
      transport.send({
        jsonrpc: "2.0",
        id: 10,
        method: "initialize",
        params: {},
      });
      await restorationGate;
      transport.send({
        jsonrpc: "2.0",
        method: "initialized",
        params: {},
      });
    });
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
      onReconnect,
    });

    const initialConnection = transport.connect();
    const firstSocket = await getSocket(0);
    firstSocket.open();
    await initialConnection;
    firstSocket.disconnect();

    const secondSocket = await getSocket(1);
    secondSocket.open();
    await vi.waitFor(() => {
      expect(secondSocket.messages()).toEqual([
        {
          jsonrpc: "2.0",
          id: 10,
          method: "initialize",
          params: {},
        },
      ]);
    });

    const hoverRequest: JSONRPCMessage = {
      jsonrpc: "2.0",
      id: 11,
      method: "textDocument/hover",
      params: { textDocument: { uri: "file:///test.py" } },
    };
    transport.send(hoverRequest);
    expect(secondSocket.messages()).toHaveLength(1);

    finishRestoration?.();
    await vi.waitFor(() => {
      expect(secondSocket.messages()).toHaveLength(3);
    });
    expect(secondSocket.messages()).toEqual([
      {
        jsonrpc: "2.0",
        id: 10,
        method: "initialize",
        params: {},
      },
      {
        jsonrpc: "2.0",
        method: "initialized",
        params: {},
      },
      hoverRequest,
    ]);
  });

  it("replays document changes made while state restoration is in flight", async () => {
    let finishRestoration: (() => void) | undefined;
    const restorationGate = new Promise<void>((resolve) => {
      finishRestoration = resolve;
    });
    const onReconnect = vi.fn(async () => {
      transport.send({
        jsonrpc: "2.0",
        method: "textDocument/didOpen",
        params: { textDocument: { uri: "file:///test.py", version: 3 } },
      });
      await restorationGate;
    });
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
      onReconnect,
    });

    const initialConnection = transport.connect();
    const firstSocket = await getSocket(0);
    firstSocket.open();
    await initialConnection;
    firstSocket.disconnect();

    const staleChange: JSONRPCMessage = {
      jsonrpc: "2.0",
      method: "textDocument/didChange",
      params: { textDocument: { uri: "file:///test.py", version: 2 } },
    };
    transport.send(staleChange);

    const secondSocket = await getSocket(1);
    secondSocket.open();
    await vi.waitFor(() => {
      expect(onReconnect).toHaveBeenCalledTimes(1);
    });

    // The user keeps typing while the resync is still awaiting.
    const liveChange: JSONRPCMessage = {
      jsonrpc: "2.0",
      method: "textDocument/didChange",
      params: { textDocument: { uri: "file:///test.py", version: 4 } },
    };
    transport.send(liveChange);

    finishRestoration?.();
    await vi.waitFor(() => {
      expect(secondSocket.messages()).toHaveLength(2);
    });
    expect(secondSocket.messages()).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didOpen",
        params: { textDocument: { uri: "file:///test.py", version: 3 } },
      },
      liveChange,
    ]);
    expect(secondSocket.messages()).not.toContainEqual(staleChange);
  });

  it("retries failed state restoration without losing queued requests", async () => {
    const onReconnect = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(new Error("State restoration failed"))
      .mockResolvedValue(undefined);
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
      onReconnect,
      retries: 2,
      retryDelayMs: 0,
    });

    const initialConnection = transport.connect();
    const firstSocket = await getSocket(0);
    firstSocket.open();
    await initialConnection;
    firstSocket.disconnect();

    const queuedRequest: JSONRPCMessage = {
      jsonrpc: "2.0",
      id: 12,
      method: "textDocument/hover",
      params: { textDocument: { uri: "file:///test.py" } },
    };
    transport.send(queuedRequest);

    const failedRestorationSocket = await getSocket(1);
    failedRestorationSocket.open();
    const recoveredSocket = await getSocket(2);
    recoveredSocket.open();

    await vi.waitFor(() => {
      expect(onReconnect).toHaveBeenCalledTimes(2);
      expect(recoveredSocket.messages()).toEqual([queuedRequest]);
    });
    expect(failedRestorationSocket.messages()).toEqual([]);
  });

  it("abandons a restoration whose socket died instead of waiting for it", async () => {
    // A restoration awaiting a response on a dead socket only settles when the
    // LSP request times out, so recovery must not be chained to it.
    const strandedRestoration = new Promise<void>(() => {
      // never settles
    });
    const onReconnect = vi
      .fn<() => Promise<void>>()
      .mockImplementationOnce(() => strandedRestoration)
      .mockResolvedValue(undefined);
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
      onReconnect,
    });

    const initialConnection = transport.connect();
    const firstSocket = await getSocket(0);
    firstSocket.open();
    await initialConnection;
    firstSocket.disconnect();

    const secondSocket = await getSocket(1);
    secondSocket.open();
    await vi.waitFor(() => {
      expect(onReconnect).toHaveBeenCalledTimes(1);
    });

    secondSocket.disconnect();

    const thirdSocket = await getSocket(2);
    thirdSocket.open();
    await vi.waitFor(() => {
      expect(onReconnect).toHaveBeenCalledTimes(2);
    });
    expect(thirdSocket.readyState).toBe(FakeWebSocket.OPEN);
  });

  it("keeps the queued backlog when a restoration is abandoned", async () => {
    const strandedRestoration = new Promise<void>(() => {
      // never settles
    });
    const onReconnect = vi
      .fn<() => Promise<void>>()
      .mockImplementationOnce(() => strandedRestoration)
      .mockResolvedValue(undefined);
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
      onReconnect,
    });

    const initialConnection = transport.connect();
    const firstSocket = await getSocket(0);
    firstSocket.open();
    await initialConnection;
    firstSocket.disconnect();

    const queuedRequest: JSONRPCMessage = {
      jsonrpc: "2.0",
      id: 21,
      method: "textDocument/hover",
      params: { textDocument: { uri: "file:///test.py" } },
    };
    transport.send(queuedRequest);

    const secondSocket = await getSocket(1);
    secondSocket.open();
    await vi.waitFor(() => {
      expect(onReconnect).toHaveBeenCalledTimes(1);
    });
    // The doomed attempt detached the backlog; abandoning it must hand the
    // messages back rather than strand them.
    secondSocket.disconnect();

    const thirdSocket = await getSocket(2);
    thirdSocket.open();
    await vi.waitFor(() => {
      expect(thirdSocket.messages()).toEqual([queuedRequest]);
    });
  });

  it("keeps inbound subscriptions active after reconnection", async () => {
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
    });
    const inbound = vi.fn();
    transport.onMessage(inbound);
    const initialConnection = transport.connect();
    const firstSocket = await getSocket(0);
    firstSocket.open();
    await initialConnection;

    firstSocket.disconnect();
    const secondSocket = await getSocket(1);
    secondSocket.open();
    const notification: JSONRPCMessage = {
      jsonrpc: "2.0",
      method: "window/logMessage",
      params: { type: 3, message: "reconnected" },
    };
    secondSocket.receive(notification);

    expect(inbound).toHaveBeenCalledWith(notification);
  });

  it("retries failed connection attempts", async () => {
    const onConnectionFailure = vi.fn();
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
      retries: 2,
      retryDelayMs: 0,
      onConnectionFailure,
    });

    const connection = transport.connect();
    const firstSocket = await getSocket(0);
    firstSocket.fail();
    const secondSocket = await getSocket(1);
    secondSocket.open();
    await connection;

    expect(secondSocket.readyState).toBe(FakeWebSocket.OPEN);
    expect(onConnectionFailure).not.toHaveBeenCalled();
  });

  it("reports the final connection failure", async () => {
    const onConnectionFailure = vi.fn();
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
      retries: 1,
      onConnectionFailure,
    });

    const connection = transport.connect();
    const socket = await getSocket(0);
    socket.fail();

    await expect(connection).rejects.toThrow(
      "WebSocket connection to ws://localhost:8080/lsp failed",
    );
    expect(onConnectionFailure).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining("failed") }),
    );
  });

  it("closes permanently and ignores later sends", async () => {
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl: () => mockWsUrl,
    });
    const connection = transport.connect();
    const socket = await getSocket(0);
    socket.open();
    await connection;

    transport.close();
    transport.send({
      jsonrpc: "2.0",
      method: "initialized",
      params: {},
    });

    expect(socket.messages()).toEqual([]);
    await expect(transport.connect()).rejects.toThrow("Transport is closed");
    expect(FakeWebSocket.instances).toHaveLength(1);
  });
});
