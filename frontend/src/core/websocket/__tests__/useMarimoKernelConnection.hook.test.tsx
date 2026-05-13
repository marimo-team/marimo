/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider as JotaiProvider } from "jotai";
import type React from "react";
import { ErrorBoundary } from "react-error-boundary";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/core/websocket/useWebSocket", async () => {
  const actual =
    await vi.importActual<typeof import("../useWebSocket")>("../useWebSocket");
  return {
    ...actual,
    useConnectionTransport: vi.fn(),
  };
});

vi.mock("@/core/runtime/config", async () => {
  const actual = await vi.importActual<typeof import("@/core/runtime/config")>(
    "@/core/runtime/config",
  );
  return {
    ...actual,
    useRuntimeManager: vi.fn(),
  };
});

import { useRuntimeManager } from "@/core/runtime/config";
import { connectionAtom } from "../../network/connection";
import type { SessionId } from "../../kernel/session";
import { WebSocketClosedReason, WebSocketState } from "../types";
import { useMarimoKernelConnection } from "../useMarimoKernelConnection";
import { useConnectionTransport } from "../useWebSocket";

interface MockTransport {
  readyState: 0 | 1 | 2 | 3;
  retryCount: number;
  reconnect: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  addEventListener: ReturnType<typeof vi.fn>;
  removeEventListener: ReturnType<typeof vi.fn>;
}

function makeTransport(
  readyState: 0 | 1 | 2 | 3 = WebSocket.CLOSED,
): MockTransport {
  return {
    readyState,
    retryCount: 0,
    reconnect: vi.fn(),
    close: vi.fn(),
    send: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
}

function makeRuntimeManager(isHealthy = vi.fn().mockResolvedValue(true)) {
  return {
    isHealthy,
    getWsURL: () => new URL("ws://localhost/ws"),
    waitForHealthy: vi.fn().mockResolvedValue(undefined),
    isSameOrigin: true,
  };
}

describe("useMarimoKernelConnection.reconnect()", () => {
  let transport: MockTransport;
  let isHealthy: ReturnType<typeof vi.fn>;
  let store: ReturnType<typeof createStore>;

  beforeEach(() => {
    transport = makeTransport(WebSocket.CLOSED);
    isHealthy = vi.fn().mockResolvedValue(true);
    store = createStore();
    store.set(connectionAtom, {
      state: WebSocketState.CLOSED,
      code: WebSocketClosedReason.KERNEL_DISCONNECTED,
      reason: "kernel not found",
    });
    vi.mocked(useConnectionTransport).mockReturnValue(transport);
    vi.mocked(useRuntimeManager).mockReturnValue(
      makeRuntimeManager(isHealthy) as unknown as ReturnType<
        typeof useRuntimeManager
      >,
    );
  });

  function renderUseHook() {
    const wrapper: React.FC<React.PropsWithChildren> = ({ children }) => (
      <JotaiProvider store={store}>
        <ErrorBoundary fallback={null}>{children}</ErrorBoundary>
      </JotaiProvider>
    );
    return renderHook(
      () =>
        useMarimoKernelConnection({
          sessionId: "test-session" as SessionId,
          autoInstantiate: false,
          setCells: () => {},
        }),
      { wrapper },
    );
  }

  it("is a no-op when the transport is already OPEN", async () => {
    transport.readyState = WebSocket.OPEN;
    const { result } = renderUseHook();
    await act(async () => {
      await result.current.reconnect();
    });
    expect(isHealthy).not.toHaveBeenCalled();
    expect(transport.reconnect).not.toHaveBeenCalled();
  });

  it("is a no-op when the transport is already CONNECTING", async () => {
    transport.readyState = WebSocket.CONNECTING;
    const { result } = renderUseHook();
    await act(async () => {
      await result.current.reconnect();
    });
    expect(isHealthy).not.toHaveBeenCalled();
    expect(transport.reconnect).not.toHaveBeenCalled();
  });

  it("probes /health and reconnects when the runtime is healthy", async () => {
    isHealthy.mockResolvedValue(true);
    const { result } = renderUseHook();
    await act(async () => {
      await result.current.reconnect();
    });
    expect(isHealthy).toHaveBeenCalledOnce();
    expect(transport.reconnect).toHaveBeenCalledOnce();
    expect(store.get(connectionAtom)).toEqual({
      state: WebSocketState.CONNECTING,
    });
  });

  it("transitions to CLOSED and does not call ws.reconnect when the probe fails", async () => {
    isHealthy.mockResolvedValue(false);
    const { result } = renderUseHook();
    await act(async () => {
      await result.current.reconnect();
    });
    expect(isHealthy).toHaveBeenCalledOnce();
    expect(transport.reconnect).not.toHaveBeenCalled();
    expect(store.get(connectionAtom)).toEqual({
      state: WebSocketState.CLOSED,
      code: WebSocketClosedReason.KERNEL_DISCONNECTED,
      reason: "kernel not found",
    });
  });
});
