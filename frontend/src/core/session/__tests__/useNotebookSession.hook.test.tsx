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

vi.mock("../backend", () => ({
  createEditorBackend: vi.fn(),
}));

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
import { Deferred } from "@/utils/Deferred";
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
import { generateSessionId } from "../../kernel/session";
import { RuntimeManager } from "../../runtime/runtime";
import { WebSocketClosedReason, ConnectionState } from "../types";
import { classifyCloseEvent } from "../../transports/connection-state";
import { createEditorBackend } from "../backend";
import {
  fakeBackend,
  fixtureMessages,
} from "../../notebook/replica/__tests__/fixtures";
import { useNotebookSession } from "../useNotebookSession";
import { type NotebookTransport, StreamStopped } from "@marimo-team/client";

const SESSION_ID = generateSessionId();

/** One connection the fake transport opened. */
interface Attempt {
  open(): void;
  receive(message: unknown): void;
  drop(): void;
  stop(error: StreamStopped): void;
}

/** A transport the test drives, one connection at a time. */
function makeTransport() {
  const attempts: Attempt[] = [];
  const transport: NotebookTransport = ({ signal }, handlers) =>
    new Promise((resolve, reject) => {
      attempts.push({
        open: handlers.open,
        receive: handlers.message,
        drop: resolve,
        stop: reject,
      });
      signal.addEventListener("abort", () => resolve(), { once: true });
    });
  return { transport, attempts };
}

type FakeTransport = ReturnType<typeof makeTransport>;

/** Use a fake transport for the next session the hook follows. */
function withTransport(fake: FakeTransport = makeTransport()) {
  vi.mocked(createEditorBackend).mockImplementation(({ checkHealth }) =>
    fakeBackend({ transport: fake.transport, checkHealth }),
  );
  return fake;
}

/** Let the stream open its first connection. */
const started = () => act(() => Promise.resolve());

/** Drive the latest connection the fake transport opened. */
function connection(fake: FakeTransport) {
  const current = () => {
    const attempt = fake.attempts.at(-1);
    if (attempt === undefined) {
      throw new Error("No connection was opened");
    }
    return attempt;
  };
  return {
    open: () => current().open(),
    receive: (message: unknown) => current().receive(message),
    /** Deliver a notification as the session routes frame it. */
    send: (notification: unknown) =>
      current().receive({ event: "marimo", data: { marimo: notification } }),
    /** End the connection so the stream reconnects. */
    drop: () => current().drop(),
    /** Close the connection with a reason the editor treats as final. */
    close: (reason: string) =>
      current().stop(
        new StreamStopped(reason, {
          cause: classifyCloseEvent({ reason }).status,
        }),
      ),
  };
}

function makeRuntimeManager(
  reconcileFromHealth = vi.fn<() => Promise<boolean>>().mockResolvedValue(true),
) {
  const runtime = new RuntimeManager(
    { url: "http://localhost", lazy: true },
    true,
  );
  vi.spyOn(runtime, "reconcileFromHealth").mockImplementation(
    reconcileFromHealth,
  );
  vi.spyOn(runtime, "probeHealth").mockResolvedValue(true);
  vi.spyOn(runtime, "getWsURL").mockReturnValue(new URL("ws://localhost/ws"));
  // Keep the initial connection pending; these tests exercise session retries.
  vi.spyOn(runtime, "waitForHealthy").mockReturnValue(
    new Deferred<void>().promise,
  );
  vi.spyOn(runtime, "isSameOrigin", "get").mockReturnValue(false);
  return runtime;
}

function renderConnectionHook(
  store: ReturnType<typeof createStore>,
  { reactStrictMode = false } = {},
) {
  const wrapper: React.FC<React.PropsWithChildren> = ({ children }) => (
    <JotaiProvider store={store}>
      <ErrorBoundary fallback={null}>{children}</ErrorBoundary>
    </JotaiProvider>
  );
  return renderHook(
    () =>
      useNotebookSession({
        sessionId: SESSION_ID,
        autoInstantiate: false,
      }),
    { wrapper, reactStrictMode },
  );
}

describe("useNotebookSession.reconnect()", () => {
  let fake: FakeTransport;
  let isHealthy: Mock<() => Promise<boolean>>;
  let store: ReturnType<typeof createStore>;

  beforeEach(() => {
    fake = withTransport();
    isHealthy = vi.fn<() => Promise<boolean>>().mockResolvedValue(true);
    store = createStore();
    store.set(connectionAtom, {
      state: ConnectionState.CLOSED,
      code: WebSocketClosedReason.KERNEL_DISCONNECTED,
      reason: "kernel not found",
    });
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager(isHealthy));
  });

  async function renderStopped() {
    const hook = renderConnectionHook(store);
    await started();
    await act(async () => connection(fake).close("MARIMO_SHUTDOWN"));
    return hook;
  }

  it.each(["connecting", "connected"])(
    "is a no-op while the stream is %s",
    async (state) => {
      const { result } = renderConnectionHook(store);
      await started();
      if (state === "connected") {
        act(() => connection(fake).open());
      }
      await act(async () => {
        await result.current.reconnect();
      });
      expect(isHealthy).not.toHaveBeenCalled();
      expect(fake.attempts).toHaveLength(1);
    },
  );

  it("probes /health and reconnects when the runtime is healthy", async () => {
    isHealthy.mockResolvedValue(true);
    const { result } = await renderStopped();
    await act(async () => {
      await result.current.reconnect();
    });
    expect(isHealthy).toHaveBeenCalledOnce();
    expect(fake.attempts).toHaveLength(2);
    expect(store.get(connectionAtom)).toEqual({
      state: ConnectionState.CONNECTING,
    });
  });

  it("transitions to CLOSED and does not reconnect when the probe fails", async () => {
    isHealthy.mockResolvedValue(false);
    const { result } = await renderStopped();
    await act(async () => {
      await result.current.reconnect();
    });
    expect(isHealthy).toHaveBeenCalledOnce();
    expect(fake.attempts).toHaveLength(1);
    expect(store.get(connectionAtom)).toEqual({
      state: ConnectionState.CLOSED,
      code: WebSocketClosedReason.KERNEL_DISCONNECTED,
      reason: "kernel not found",
    });
  });
});

describe("useNotebookSession document model", () => {
  it("keeps drafts while the connection drops and discards them when the session ends", async () => {
    const fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    const store = createStore();
    const { result, unmount } = renderConnectionHook(store, {
      reactStrictMode: true,
    });
    await started();
    act(() => {
      connection(fake).open();
      fixtureMessages("notebook-events.sse").forEach(connection(fake).receive);
    });
    const model = result.current.documentModel;
    const code = () => store.get(model.documentAtom)?.cells.get("c1")?.code;
    act(() => store.set(model.editAtom, (tx) => tx.setCode("c1", "local")));
    expect(code()).toBe("local");

    await act(async () => connection(fake).drop());
    expect(result.current.documentModel).toBe(model);
    expect(code()).toBe("local");

    unmount();
    expect(code()).toBeUndefined();
    await expect(model.flush()).rejects.toThrow("not started");
  });

  it("follows the host document into the notebook's cells", async () => {
    const fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    const store = createStore();
    const { result, unmount } = renderConnectionHook(store);
    await started();
    act(() => {
      connection(fake).open();
      fixtureMessages("notebook-events.sse").forEach(connection(fake).receive);
    });

    let notebook = store.get(notebookAtom);
    expect(notebook.cellIds.inOrderIds).toEqual(["c1", "c3", "k7f2"]);
    expect(notebook.cellData[cellId("k7f2")]).toMatchObject({
      code: "y = x * 2",
      config: { hide_code: true },
    });

    const model = result.current.documentModel;
    act(() => store.set(model.editAtom, (tx) => tx.setCode("c3", "x = 42")));
    notebook = store.get(notebookAtom);
    expect(notebook.cellData[cellId("c3")].code).toBe("x = 42");

    unmount();
  });
});

describe("useNotebookSession messages", () => {
  let store: ReturnType<typeof createStore>;
  let fake: FakeTransport;

  beforeEach(async () => {
    store = createStore();
    fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    renderConnectionHook(store);
    await started();
  });

  function receive(payload: unknown) {
    act(() => connection(fake).receive(payload));
  }

  it("records completion of the initial run", () => {
    const notification = {
      op: "completed-run",
      run_id: null,
      outcome: "succeeded",
      error: null,
    } satisfies NotificationPayload["data"];
    expect(store.get(initialRunCompletedAtom)).toBe(false);
    receive({ id: "42", event: "marimo", data: { marimo: notification } });
    expect(store.get(initialRunCompletedAtom)).toBe(true);
  });
});

it.each(["kernel-ready", "reconnected"])(
  "waits for %s before marking the session connected",
  async (op) => {
    const store = createStore();
    store.set(connectionAtom, { state: ConnectionState.CONNECTING });
    const fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    renderConnectionHook(store);
    await started();
    const conn = connection(fake);

    await act(async () => conn.open());
    expect(store.get(connectionAtom).state).toBe(ConnectionState.CONNECTING);

    act(() =>
      conn.send({
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
      }),
    );
    expect(store.get(connectionAtom).state).toBe(ConnectionState.OPEN);
  },
);

describe("connection notice", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  async function renderNotice() {
    const store = createStore();
    store.set(connectionAtom, { state: ConnectionState.CONNECTING });
    const fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    const Connection = () => {
      const { reconnect } = useNotebookSession({
        sessionId: SESSION_ID,
        autoInstantiate: false,
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
    await started();
    const conn = connection(fake);
    // Messages arrive on an open connection.
    act(() => conn.open());
    const send = (data: NotificationPayload["data"]) =>
      act(() => conn.send(data));
    return { store, fake, conn, send };
  }

  it("keeps elapsed time across startup phases and leaves reconnection to the footer once cells are available", async () => {
    const { store, conn, send } = await renderNotice();
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
    send({
      op: "startup-progress",
      phase: "starting-kernel",
      logs: "",
      log_mode: "replace",
    });
    expect(screen.getByRole("status")).toHaveTextContent("Starting kernel");
    expect(screen.getByText("Elapsed 35s")).toBeInTheDocument();
    act(() =>
      store.set(
        notebookAtom,
        MockNotebook.notebookState({
          cellData: { [cellId("test")]: { code: "answer = 42" } },
        }),
      ),
    );
    expect(
      screen.getByRole("button", { name: "Starting kernel… Open Packages" }),
    ).toBeVisible();
    expect(screen.queryByText(/Elapsed/)).not.toBeInTheDocument();
    send({ op: "reconnected" });
    expect(
      screen.queryByRole("region", { name: "Notebook startup" }),
    ).not.toBeInTheDocument();
    await act(async () => conn.drop());
    act(() => vi.advanceTimersByTime(500));
    expect(store.get(connectionAtom)).toEqual({
      state: ConnectionState.CONNECTING,
      phase: "reconnecting",
    });
    expect(
      screen.queryByRole("region", { name: "Notebook startup" }),
    ).not.toBeInTheDocument();
  });

  it("restores startup output before appending live chunks and resets it for a new attempt", async () => {
    const { store, send } = await renderNotice();
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
    const { store, conn, send } = await renderNotice();
    send({ op: "reconnected" });
    send({
      op: "startup-progress",
      phase: "starting-kernel",
      logs: "Kernel startup output\n",
      log_mode: "replace",
    });
    expect(store.get(connectionAtom)).toEqual({ state: ConnectionState.OPEN });
    expect(store.get(startupProgressAtom)).toEqual({
      phase: "starting-kernel",
      logs: "Kernel startup output\n",
    });
    act(() => vi.advanceTimersByTime(500));
    expect(
      screen.queryByRole("region", { name: "Notebook startup" }),
    ).not.toBeInTheDocument();

    // A new connection starts from the next session's authoritative snapshot.
    await act(async () => conn.drop());
    await act(async () => vi.advanceTimersByTime(2000));
    await act(async () => conn.open());
    expect(store.get(startupProgressAtom)).toBeNull();
  });

  it("does not flash a notice when startup finishes within the delay", async () => {
    const { send } = await renderNotice();
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

  it.each(["preparing-environment", "starting-kernel"] as const)(
    "keeps a %s failure available until the user retries",
    async (phase) => {
      const { store, fake, conn, send } = await renderNotice();
      send({ op: "startup-progress", phase, logs: "", log_mode: "replace" });
      const error = "A full diagnostic\nwith <stderr> details";
      send({ op: "kernel-startup-error", error });
      await act(async () => conn.close("MARIMO_KERNEL_STARTUP_ERROR"));
      expect(screen.getByRole("status")).toHaveTextContent(
        "Kernel failed to start",
      );
      act(() => vi.advanceTimersByTime(30_000));
      expect(screen.getByRole("status")).toHaveTextContent(
        "Kernel failed to start",
      );
      expect(screen.getByLabelText("Error details")).toHaveTextContent(error, {
        normalizeWhitespace: false,
      });
      expect(fake.attempts).toHaveLength(1);
      await act(async () =>
        fireEvent.click(screen.getByRole("button", { name: "Try again" })),
      );
      expect(fake.attempts).toHaveLength(2);
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

it("replaces environment state from snapshots, then continues live progress", async () => {
  const store = createStore();
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  function receive(data: NotificationPayload["data"]) {
    act(() => connection(fake).send(data));
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
