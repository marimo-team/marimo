/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
} from "@testing-library/react";
import { createStore, Provider as JotaiProvider } from "jotai";
import type React from "react";
import { ErrorBoundary } from "react-error-boundary";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  type Mock,
  vi,
} from "vitest";

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

import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { alertAtom, getPackageAlert } from "@/core/alerts/state";
import { notebookAtom } from "@/core/cells/cells";
import { AppConfigSchema } from "@/core/config/config-schema";
import { ConnectionNotice } from "@/components/editor/alerts/connection-notice";
import { kernelStartupErrorAtom } from "@/core/errors/state";
import type { NotificationPayload } from "@/core/kernel/messages";
import { useRuntimeManager } from "@/core/runtime/config";
import { initialRunCompletedAtom } from "../../kernel/state";
import { connectionAtom, startupProgressAtom } from "../../network/connection";
import type { SessionId } from "../../kernel/session";
import { WebSocketClosedReason, WebSocketState } from "../types";
import type { IConnectionTransport } from "../transports/transport";
import { useMarimoKernelConnection } from "../useMarimoKernelConnection";
import { useConnectionTransport } from "../useWebSocket";

interface MockTransport {
  readyState: 0 | 1 | 2 | 3;
  reconnect: Mock<IConnectionTransport["reconnect"]>;
  close: Mock<IConnectionTransport["close"]>;
  send: Mock<IConnectionTransport["send"]>;
  addEventListener: Mock<IConnectionTransport["addEventListener"]>;
  removeEventListener: Mock<IConnectionTransport["removeEventListener"]>;
}

function makeTransport(
  readyState: 0 | 1 | 2 | 3 = WebSocket.CLOSED,
): MockTransport {
  return {
    readyState,
    reconnect: vi.fn(),
    close: vi.fn(),
    send: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
}

function makeRuntimeManager(
  reconcileFromHealth = vi.fn<() => Promise<boolean>>().mockResolvedValue(true),
) {
  return {
    reconcileFromHealth,
    probeHealth: vi.fn().mockResolvedValue(true),
    getWsURL: () => new URL("ws://localhost/ws"),
    waitForHealthy: vi.fn().mockResolvedValue(undefined),
    isSameOrigin: true,
  };
}

function renderConnectionHook(store: ReturnType<typeof createStore>) {
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

describe("useMarimoKernelConnection.reconnect()", () => {
  let transport: MockTransport;
  let isHealthy: Mock<() => Promise<boolean>>;
  let store: ReturnType<typeof createStore>;

  beforeEach(() => {
    transport = makeTransport(WebSocket.CLOSED);
    isHealthy = vi.fn<() => Promise<boolean>>().mockResolvedValue(true);
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
    return renderConnectionHook(store);
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

describe("useMarimoKernelConnection messages", () => {
  it("records completion of the initial run", () => {
    const store = createStore();
    vi.mocked(useConnectionTransport).mockClear();
    vi.mocked(useConnectionTransport).mockReturnValue(
      makeTransport(WebSocket.OPEN),
    );
    vi.mocked(useRuntimeManager).mockReturnValue(
      makeRuntimeManager() as unknown as ReturnType<typeof useRuntimeManager>,
    );
    renderConnectionHook(store);

    const options = vi.mocked(useConnectionTransport).mock.calls.at(-1)?.[0];
    expect(store.get(initialRunCompletedAtom)).toBe(false);
    act(() => {
      options?.onMessage(
        new MessageEvent("message", {
          data: JSON.stringify({
            op: "completed-run",
            data: { op: "completed-run", run_id: null },
          }),
        }),
      );
    });
    expect(store.get(initialRunCompletedAtom)).toBe(true);
  });
});

it.each(["kernel-ready", "reconnected"])(
  "waits for %s before marking the session connected",
  async (op) => {
    const store = createStore();
    store.set(connectionAtom, { state: WebSocketState.CONNECTING });
    vi.mocked(useConnectionTransport).mockClear();
    vi.mocked(useConnectionTransport).mockReturnValue(
      makeTransport(WebSocket.OPEN),
    );
    vi.mocked(useRuntimeManager).mockReturnValue(
      makeRuntimeManager() as unknown as ReturnType<typeof useRuntimeManager>,
    );
    renderConnectionHook(store);
    const options = vi.mocked(useConnectionTransport).mock.calls.at(-1)![0];

    await act(async () => {
      await options.onOpen(new Event("open"));
    });
    expect(store.get(connectionAtom).state).toBe(WebSocketState.CONNECTING);

    act(() => {
      options.onMessage(
        new MessageEvent("message", {
          data: JSON.stringify({
            op,
            data: {
              op,
              cell_ids: [],
              codes: [],
              names: [],
              configs: [],
              layout: null,
              resumed: true,
              ui_values: {},
              last_executed_code: {},
              last_execution_time: {},
              app_config: { width: "normal" },
              kiosk: false,
              capabilities: { terminal: false },
              auto_instantiated: false,
              consumer_capabilities: { edit: true, interact: true },
            },
          }),
        }),
      );
    });
    expect(store.get(connectionAtom).state).toBe(WebSocketState.OPEN);
  },
);

describe("connection notice", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  function renderNotice() {
    const store = createStore();
    store.set(connectionAtom, { state: WebSocketState.CONNECTING });
    const transport = makeTransport(WebSocket.OPEN);
    vi.mocked(useConnectionTransport).mockReturnValue(transport);
    vi.mocked(useRuntimeManager).mockReturnValue(
      makeRuntimeManager() as unknown as ReturnType<typeof useRuntimeManager>,
    );
    const Connection = () => {
      const { reconnect } = useMarimoKernelConnection({
        sessionId: "test-session" as SessionId,
        autoInstantiate: false,
        setCells: () => {},
      });
      return (
        <ConnectionNotice
          appConfig={AppConfigSchema.parse({})}
          onRetry={reconnect}
        />
      );
    };
    render(
      <JotaiProvider store={store}>
        <ErrorBoundary fallback={null}>
          <Connection />
        </ErrorBoundary>
      </JotaiProvider>,
    );
    const options = vi.mocked(useConnectionTransport).mock.calls.at(-1)![0];
    const send = (data: NotificationPayload["data"]) =>
      act(() => {
        options.onMessage(
          new MessageEvent("message", {
            data: JSON.stringify({ op: data.op, data }),
          }),
        );
      });
    return { store, transport, options, send };
  }

  it("keeps elapsed time across startup phases and leaves reconnection to the footer once cells are available", () => {
    const { store, options, send } = renderNotice();
    send({
      op: "startup-progress",
      phase: "preparing-environment",
      logs: "",
      log_mode: "replace",
    });
    expect(
      screen.queryByRole("region", { name: "Notebook startup" }),
    ).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(500));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Preparing environment",
    );
    act(() => vi.advanceTimersByTime(35_000));
    expect(screen.getByText("Elapsed 35s")).toBeInTheDocument();
    act(() =>
      store.set(
        notebookAtom,
        MockNotebook.notebookState({
          cellData: { [cellId("test")]: { code: "answer = 42" } },
        }),
      ),
    );
    send({
      op: "startup-progress",
      phase: "starting-kernel",
      logs: "",
      log_mode: "replace",
    });
    expect(screen.getByRole("status")).toHaveTextContent("Starting kernel");
    expect(screen.getByText("Elapsed 35s")).toBeInTheDocument();
    send({ op: "reconnected" });
    expect(
      screen.queryByRole("region", { name: "Notebook startup" }),
    ).not.toBeInTheDocument();
    act(() => options.onClose(new CloseEvent("close")));
    act(() => vi.advanceTimersByTime(500));
    expect(store.get(connectionAtom)).toEqual({
      state: WebSocketState.CONNECTING,
      phase: "reconnecting",
    });
    expect(
      screen.queryByRole("region", { name: "Notebook startup" }),
    ).not.toBeInTheDocument();
  });

  it("restores startup output before appending live chunks and resets it for a new attempt", () => {
    const { store, send } = renderNotice();
    const snapshot = {
      op: "startup-progress",
      phase: "starting-kernel",
      logs: "Downloading runtime\n",
      log_mode: "replace",
    } as const;
    send(snapshot);
    send(snapshot);
    const connection = store.get(connectionAtom);
    send({ ...snapshot, logs: "Loading kernel\n", log_mode: "append" });
    expect(store.get(startupProgressAtom)).toEqual({
      phase: "starting-kernel",
      logs: "Downloading runtime\nLoading kernel\n",
    });
    expect(store.get(connectionAtom)).toBe(connection);
    expect(getPackageAlert(store.get(alertAtom))).toBeNull();

    send({ ...snapshot, phase: "preparing-environment", logs: "" });
    expect(store.get(startupProgressAtom)).toEqual({
      phase: "preparing-environment",
      logs: "",
    });
  });

  it("restores completed startup output without putting a connected kernel back into startup", async () => {
    const { store, options, send } = renderNotice();
    send({ op: "reconnected" });
    send({
      op: "startup-progress",
      phase: "starting-kernel",
      logs: "Kernel startup output\n",
      log_mode: "replace",
    });
    expect(store.get(connectionAtom)).toEqual({ state: WebSocketState.OPEN });
    expect(store.get(startupProgressAtom)).toEqual({
      phase: "starting-kernel",
      logs: "Kernel startup output\n",
    });
    act(() => vi.advanceTimersByTime(500));
    expect(
      screen.queryByRole("region", { name: "Notebook startup" }),
    ).not.toBeInTheDocument();

    // A new transport starts from the next session's authoritative snapshot.
    await act(async () => options.onOpen(new Event("open")));
    expect(store.get(startupProgressAtom)).toBeNull();
  });

  it("does not flash a notice when startup finishes within the delay", () => {
    const { send } = renderNotice();
    send({
      op: "startup-progress",
      phase: "preparing-environment",
      logs: "",
      log_mode: "replace",
    });
    act(() => vi.advanceTimersByTime(200));
    send({
      op: "startup-progress",
      phase: "starting-kernel",
      logs: "",
      log_mode: "replace",
    });
    act(() => vi.advanceTimersByTime(200));
    expect(
      screen.queryByRole("region", { name: "Notebook startup" }),
    ).not.toBeInTheDocument();
    send({ op: "reconnected" });
    act(() => vi.advanceTimersByTime(500));
    expect(
      screen.queryByRole("region", { name: "Notebook startup" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["preparing-environment", "Sandbox setup failed"],
    ["starting-kernel", "Kernel failed to start"],
  ] as const)(
    "keeps a %s failure available until the user retries",
    async (phase, title) => {
      const { store, transport, options, send } = renderNotice();
      send({ op: "startup-progress", phase, logs: "", log_mode: "replace" });
      const error = "A full diagnostic\nwith <stderr> details";
      send({ op: "kernel-startup-error", error });
      transport.readyState = WebSocket.CLOSED;
      act(() =>
        options.onClose(
          new CloseEvent("close", { reason: "MARIMO_KERNEL_STARTUP_ERROR" }),
        ),
      );
      expect(screen.getByRole("status")).toHaveTextContent(title);
      act(() => vi.advanceTimersByTime(30_000));
      expect(screen.getByRole("status")).toHaveTextContent(title);
      expect(screen.getByLabelText("Error details")).toHaveTextContent(error, {
        normalizeWhitespace: false,
      });
      expect(transport.reconnect).not.toHaveBeenCalled();
      await act(async () =>
        fireEvent.click(screen.getByRole("button", { name: "Try again" })),
      );
      expect(transport.reconnect).toHaveBeenCalledOnce();
      expect(store.get(kernelStartupErrorAtom)).toBeNull();
      expect(
        screen.queryByRole("button", { name: "Try again" }),
      ).not.toBeInTheDocument();
      send({
        op: "startup-progress",
        phase: "preparing-environment",
        logs: "",
        log_mode: "replace",
      });
      act(() => vi.advanceTimersByTime(500));
      expect(screen.getByRole("status")).toHaveTextContent(
        "Preparing environment",
      );
      expect(screen.getByText("Elapsed 0s")).toBeInTheDocument();
    },
  );
});

it("replaces environment state from snapshots, then continues live progress", () => {
  const store = createStore();
  vi.mocked(useConnectionTransport).mockClear();
  vi.mocked(useConnectionTransport).mockReturnValue(
    makeTransport(WebSocket.OPEN),
  );
  vi.mocked(useRuntimeManager).mockReturnValue(
    makeRuntimeManager() as unknown as ReturnType<typeof useRuntimeManager>,
  );
  renderConnectionHook(store);
  const options = vi.mocked(useConnectionTransport).mock.calls.at(-1)?.[0];
  function receive(data: NotificationPayload["data"]) {
    act(() =>
      options?.onMessage(
        new MessageEvent("message", {
          data: JSON.stringify({ op: data.op, data }),
        }),
      ),
    );
  }
  receive({
    op: "environment-operation",
    source: "kernel",
    operation_id: "old",
    action: "install",
    status: { kind: "running" },
    packages: { pandas: "running" },
    logs: { pandas: "stale" },
    log_mode: "append",
  });
  const operation = {
    operation_id: "new",
    action: "install",
    source: "kernel",
    status: { kind: "running" },
    packages: { numpy: "running" },
    logs: { numpy: "Downloading\n" },
  } as const;
  const serverOperation = {
    ...operation,
    operation_id: "server",
    action: "install",
    source: "server",
    status: { kind: "succeeded" },
    packages: { numpy: "succeeded" },
    logs: { numpy: "Server logs\n" },
  } as const;
  receive({
    op: "environment-state",
    source: "server",
    state: {
      restart_required: false,
      operations: [serverOperation],
    },
  });
  const snapshot = {
    op: "environment-state",
    source: "kernel",
    state: { restart_required: false, operations: [operation] },
  } as const;
  // Receiving a snapshot twice must not duplicate logs.
  receive({
    ...snapshot,
    state: { ...snapshot.state, operations: [operation] },
  });
  receive({
    ...snapshot,
    state: { ...snapshot.state, operations: [operation] },
  });
  receive({
    op: "environment-operation",
    operation_id: "new",
    action: "install",
    source: "kernel",
    status: { kind: "failed", error: "Network unavailable" },
    packages: { numpy: "running" },
    logs: { numpy: "Failed\n" },
    log_mode: "append",
  });
  expect(getPackageAlert(store.get(alertAtom))).toEqual({
    ...operation,
    id: "new",
    kind: "environment",
    restartRequired: false,
    status: { kind: "failed", error: "Network unavailable" },
    logs: { numpy: "Downloading\nFailed\n" },
  });
  receive({
    op: "environment-state",
    source: "kernel",
    state: {
      restart_required: false,
      operations: [],
    },
  });
  // Clearing the active environment must not promote an old server success.
  expect(getPackageAlert(store.get(alertAtom))).toBeNull();
  expect(store.get(alertAtom).environments.server.operations).toEqual([
    serverOperation,
  ]);
  receive({
    op: "environment-state",
    source: "server",
    state: {
      restart_required: false,
      operations: [],
    },
  });
  expect(getPackageAlert(store.get(alertAtom))).toBeNull();
  expect(store.get(alertAtom).environments).toEqual({
    kernel: { restart_required: false, operations: [] },
    server: { restart_required: false, operations: [] },
  });
});
