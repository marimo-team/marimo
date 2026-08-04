/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";
import { LazyWebsocketTransport } from "../transport";

vi.mock("@/utils/Logger", () => ({
  Logger: Mocks.logger(),
}));

class FakeWebSocket {
  static readonly OPEN = 1;
  static readonly CLOSED = 3;
  static readonly instances: FakeWebSocket[] = [];

  readonly sent: string[] = [];
  readyState = 0;
  readonly url: string;
  private readonly listeners = new Map<
    string,
    Set<(event: Record<string, never>) => void>
  >();

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  addEventListener(
    type: string,
    listener: (event: Record<string, never>) => void,
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
    this.emit("close");
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.emit("open");
  }

  fail() {
    this.emit("error");
  }

  private emit(type: string) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({});
    }
  }
}

async function getSocket(index: number): Promise<FakeWebSocket> {
  await vi.waitFor(() => {
    expect(FakeWebSocket.instances.length).toBeGreaterThan(index);
  });
  return FakeWebSocket.instances[index];
}

describe("LazyWebsocketTransport", () => {
  const mockWsUrl = "ws://localhost:8080/copilot";

  beforeEach(() => {
    FakeWebSocket.instances.length = 0;
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("waits for Copilot prerequisites before connecting", async () => {
    let ready: (() => void) | undefined;
    const waitForReady = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          ready = resolve;
        }),
    );
    const transport = new LazyWebsocketTransport({
      getWsUrl: () => mockWsUrl,
      waitForReady,
      showError: vi.fn(),
      retryDelayMs: 0,
    });

    const connection = transport.connect();
    expect(waitForReady).toHaveBeenCalledTimes(1);
    expect(FakeWebSocket.instances).toHaveLength(0);

    ready?.();
    const socket = await getSocket(0);
    socket.open();
    await connection;

    expect(socket.url).toBe(mockWsUrl);
  });

  it("shows a user-facing error after the final retry", async () => {
    const showError = vi.fn();
    const transport = new LazyWebsocketTransport({
      getWsUrl: () => mockWsUrl,
      waitForReady: vi.fn().mockResolvedValue(undefined),
      showError,
      retries: 2,
      retryDelayMs: 0,
    });

    const connection = transport.connect();
    (await getSocket(0)).fail();
    (await getSocket(1)).fail();

    await expect(connection).rejects.toThrow(
      "WebSocket connection to ws://localhost:8080/copilot failed",
    );
    expect(showError).toHaveBeenCalledWith(
      "GitHub Copilot Connection Error",
      "Failed to connect to GitHub Copilot. Please check your settings and try again.\n\nWebSocket connection to ws://localhost:8080/copilot failed",
    );
  });

  it("inherits reconnect callbacks for Copilot re-initialization", async () => {
    const transport = new LazyWebsocketTransport({
      getWsUrl: () => mockWsUrl,
      waitForReady: vi.fn().mockResolvedValue(undefined),
      showError: vi.fn(),
      retryDelayMs: 0,
    });
    const onReconnect = vi.fn().mockResolvedValue(undefined);
    transport.onReconnect = onReconnect;

    const initialConnection = transport.connect();
    const firstSocket = await getSocket(0);
    firstSocket.open();
    await initialConnection;
    firstSocket.close();

    const secondSocket = await getSocket(1);
    secondSocket.open();
    await vi.waitFor(() => {
      expect(onReconnect).toHaveBeenCalledTimes(1);
    });
  });
});
