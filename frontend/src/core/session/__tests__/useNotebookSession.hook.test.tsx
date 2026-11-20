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
import { stagedAICellsAtom } from "@/core/ai/staged-cells";
import { cellRuntimeAtom } from "@/core/cells/cells";
import { clearCellConsoleOutputAtom } from "@/core/cells/actions";
import { notebookAtom } from "@/core/cells/cells";
import { SCRATCH_CELL_ID } from "@/core/cells/ids";
import {
  breakpointsAtom,
  pendingPdbInputAtom,
} from "@/core/codemirror/cells/debugger-state";
import { AppConfigSchema } from "@/core/config/config-schema";
import { hasBlockingStdinAtom } from "@/components/editor/stdin-blocking-alert";
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
  fixtureEvents,
  fixtureMessages,
} from "../../notebook/replica/__tests__/fixtures";
import { MockExecutions } from "@/__mocks__/executions";
import { VirtualFileTracker } from "@/core/static/virtual-file-tracker";
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
    /** Deliver a snapshot of the notebook, ending in the stream's `ready`. */
    ready: () => {
      for (const message of fixtureMessages("notebook-events.sse")) {
        current().receive(message);
        if (message.event === "ready") {
          break;
        }
      }
    },
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
  const runtime = new RuntimeManager({ url: "http://localhost" });
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

  it("removes deleted cells from pending AI review while retaining surviving edits", async () => {
    const fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    const store = createStore();
    const { result, unmount } = renderConnectionHook(store);
    await started();
    act(() => {
      connection(fake).open();
      fixtureMessages("notebook-events.sse").forEach(connection(fake).receive);
    });
    const removed = cellId("c3");
    const retained = cellId("k7f2");
    act(() =>
      store.set(
        stagedAICellsAtom,
        new Map([
          [removed, { type: "add_cell" }],
          [retained, { type: "add_cell" }],
        ]),
      ),
    );
    act(() =>
      store.set(result.current.documentModel.editAtom, (tx) =>
        tx.deleteCell(removed),
      ),
    );
    expect(store.get(notebookAtom).cellIds).not.toContain(removed);
    expect(store.get(stagedAICellsAtom)).toEqual(
      new Map([[retained, { type: "add_cell" }]]),
    );
    unmount();
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
    expect(notebook.cellIds).toEqual(["c1", "c3", "k7f2"]);
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

it("waits for the stream's snapshot before marking the session connected", async () => {
  const store = createStore();
  store.set(connectionAtom, { state: ConnectionState.CONNECTING });
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  const conn = connection(fake);

  await act(async () => conn.open());
  expect(store.get(connectionAtom).state).toBe(ConnectionState.CONNECTING);

  // A host that is not marimo never sends kernel-ready.
  for (const message of fixtureMessages("notebook-events.sse")) {
    act(() => conn.receive(message));
    if (message.event === "ready") {
      break;
    }
    expect(store.get(connectionAtom)).toEqual({
      state: ConnectionState.CONNECTING,
    });
  }
  expect(store.get(connectionAtom)).toEqual({ state: ConnectionState.OPEN });
});

it("waits for another ready snapshot after the stream resets", async () => {
  const store = createStore();
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  const conn = connection(fake);
  act(() => {
    conn.open();
    conn.ready();
  });
  expect(store.get(connectionAtom)).toEqual({ state: ConnectionState.OPEN });

  act(() => conn.receive({ event: "reset", data: {} }));
  expect(store.get(connectionAtom)).toEqual({
    state: ConnectionState.CONNECTING,
    phase: "reconnecting",
  });

  for (const message of fixtureMessages("notebook-events.sse")) {
    act(() => conn.receive(message));
    if (message.event === "ready") {
      break;
    }
    expect(store.get(connectionAtom)).toEqual({
      state: ConnectionState.CONNECTING,
      phase: "reconnecting",
    });
  }
  expect(store.get(connectionAtom)).toEqual({ state: ConnectionState.OPEN });
});

it("does not mark a static page connected", async () => {
  window.__MARIMO_STATIC__ = { files: {} };
  try {
    const store = createStore();
    const fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    renderConnectionHook(store);
    await started();
    const conn = connection(fake);

    await act(async () => conn.open());
    act(() => conn.ready());
    expect(store.get(connectionAtom).state).not.toBe(ConnectionState.OPEN);
  } finally {
    delete window.__MARIMO_STATIC__;
  }
});

it("does not mark the session connected on kernel-ready alone", async () => {
  const store = createStore();
  store.set(connectionAtom, { state: ConnectionState.CONNECTING });
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  const conn = connection(fake);
  await act(async () => conn.open());

  act(() =>
    conn.send({
      op: "kernel-ready",
      layout: null,
      resumed: true,
      ui_values: {},
      app_config: { width: "normal" },
      kiosk: false,
      capabilities: { terminal: false },
      consumer_capabilities: { edit: true, interact: true },
    }),
  );
  expect(store.get(connectionAtom).state).toBe(ConnectionState.CONNECTING);
});

it.each(["", "latest"])(
  "restores only the latest scratch console (%j) on resume and reset",
  async (text) => {
    const store = createStore();
    const fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    renderConnectionHook(store);
    await started();
    const conn = connection(fake);
    const rows = () =>
      store
        .get(cellRuntimeAtom(SCRATCH_CELL_ID))
        .consoleOutputs.map((entry) => entry.data);
    await act(async () => conn.open());
    act(() => {
      for (const frame of fixtureMessages("notebook-events.sse")) {
        conn.receive(frame);
      }
    });
    expect(rows()).toEqual(["2\n"]);
    const scratch = {
      ...MockExecutions.execution(null, {
        status: "completed",
        depends_on: {},
        outcome: { kind: "succeeded" },
        started_at: "2026-10-01T09:21:01Z",
        completed_at: "2026-10-01T09:21:02Z",
      }),
      id: "second-scratch",
    };
    act(() => {
      conn.receive({
        event: "execution",
        data: {
          execution: {
            ...scratch,
            state: {
              status: "running",
              started_at: "2026-10-01T09:21:01Z",
            },
          },
        },
      });
      if (text) {
        conn.receive({
          event: "console",
          data: {
            console: {
              id: "second-line",
              execution_id: scratch.id,
              seq: 0,
              name: "stdout",
              text,
            },
          },
        });
      }
      conn.receive({ event: "execution", data: { execution: scratch } });
    });
    expect(rows()).toEqual(text ? [text] : []);
    const kernelReady = () =>
      conn.send({
        op: "kernel-ready",
        resumed: true,
        ui_values: {},
        layout: null,
        app_config: { width: "normal" },
        kiosk: false,
        capabilities: {},
        consumer_capabilities: { edit: true, interact: true },
      });
    act(kernelReady);
    expect(rows()).toEqual(text ? [text] : []);
    act(() => {
      conn.receive({ event: "reset", data: {} });
      for (const frame of fixtureMessages("notebook-events.sse")) {
        if (!["run", "execution", "console"].includes(frame.event)) {
          conn.receive(frame);
        }
        if (frame.event === "ready") {
          break;
        }
      }
      kernelReady();
    });
    expect(rows()).toEqual(text ? [text] : []);
  },
);

it("keeps a browser-cleared console hidden when the running execution is replayed", async () => {
  const store = createStore();
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  const conn = connection(fake);
  const rows = () =>
    store
      .get(cellRuntimeAtom(SCRATCH_CELL_ID))
      .consoleOutputs.map((row) => row.data);
  await act(async () => conn.open());
  act(() => conn.ready());
  expect(rows()).toEqual(["2\n"]);
  act(() => {
    store.set(clearCellConsoleOutputAtom, { cellId: SCRATCH_CELL_ID });
    conn.receive({ event: "reset", data: {} });
    conn.ready();
    conn.send({
      op: "kernel-ready",
      resumed: true,
      ui_values: {},
      layout: null,
      app_config: { width: "normal" },
      kiosk: false,
      capabilities: {},
      consumer_capabilities: { edit: true, interact: true },
    });
  });
  expect(rows()).toEqual([]);
  act(() =>
    conn.receive({
      event: "console",
      data: {
        console: {
          id: "new-line",
          execution_id: "e7",
          seq: 1,
          name: "stdout",
          text: "after the clear",
        },
      },
    }),
  );
  expect(rows()).toEqual(["after the clear"]);
});

it.each(["browser", "kernel"])(
  "keeps rows cleared by the %s hidden when a prompt is answered",
  async (source) => {
    const store = createStore();
    const fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    renderConnectionHook(store);
    await started();
    const conn = connection(fake);
    const cell = cellId("c1");
    const execution = MockExecutions.running(cell);
    const first = {
      id: "first",
      seq: 0,
      execution_id: execution.id,
      prompt: "first?",
      password: false,
      status: "answered",
    };
    const second = {
      ...first,
      id: "second",
      seq: 1,
      prompt: "second?",
      status: "pending",
    };
    const cleared = {
      op: "console-inputs-cleared",
      cell_id: cell,
      execution_id: execution.id,
      input_ids: [first.id],
    };
    const rows = () => store.get(cellRuntimeAtom(cell)).consoleOutputs;
    await act(async () => conn.open());
    act(() => {
      conn.ready();
      conn.receive({ event: "execution", data: { execution } });
      conn.receive({ event: "input", data: { input: first } });
      conn.receive({ event: "input", data: { input: second } });
      if (source === "browser") {
        store.set(clearCellConsoleOutputAtom, { cellId: cell });
      } else {
        conn.send(cleared);
      }
    });
    expect(store.get(hasBlockingStdinAtom)).toBe(true);
    expect(rows()).toMatchObject([{ input_id: "second", response: undefined }]);
    act(() =>
      conn.receive({
        event: "input",
        data: { input: { ...second, status: "answered" } },
      }),
    );
    expect(store.get(hasBlockingStdinAtom)).toBe(false);
    expect(rows()).toMatchObject([{ input_id: "second", response: null }]);
    if (source === "browser") {
      return;
    }
    act(() => {
      conn.send({
        op: "kernel-ready",
        resumed: true,
        ui_values: {},
        layout: null,
        app_config: { width: "normal" },
        kiosk: false,
        capabilities: {},
        consumer_capabilities: { edit: true, interact: true },
      });
      conn.send(cleared);
    });
    expect(rows()).toMatchObject([{ input_id: "second", response: null }]);
  },
);

it.each(["callback-output", "pdb-output"] as const)(
  "keeps cleared %s writes hidden on replay and shows later identical writes",
  async (op) => {
    const store = createStore();
    const fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    renderConnectionHook(store);
    await started();
    const conn = connection(fake);
    const cell = cellId("c1");
    const rows = () =>
      store.get(cellRuntimeAtom(cell)).consoleOutputs.map((row) => row.data);
    const send = (replace: boolean, ...ids: string[]) =>
      conn.send({
        op,
        cell_id: cell,
        replace,
        after_seq: ids.map(() => 0),
        entries: ids.map((command_id) => ({
          command_id,
          channel: "stdout",
          mimetype: "text/plain",
          data: "same",
          timestamp: 1,
        })),
      });
    await act(async () => conn.open());
    act(() => {
      conn.ready();
      send(false, "one");
      store.set(clearCellConsoleOutputAtom, { cellId: cell });
    });
    expect(rows()).toEqual([]);
    act(() => {
      conn.receive({ event: "reset", data: {} });
      conn.ready();
      conn.send({
        op: "kernel-ready",
        resumed: true,
        ui_values: {},
        layout: null,
        app_config: { width: "normal" },
        kiosk: false,
        capabilities: {},
        consumer_capabilities: { edit: true, interact: true },
      });
      send(true, "one", "two");
    });
    expect(rows()).toEqual(["same"]);
    act(() => {
      store.set(clearCellConsoleOutputAtom, { cellId: cell });
      // The host cleared its transcript while this editor was disconnected.
      send(true, "three");
    });
    expect(rows()).toEqual(["same"]);
  },
);

it.each(["live", "replay"])(
  "interleaves %s command output with untimed execution items",
  async (mode) => {
    const store = createStore();
    const fake = withTransport();
    vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
    renderConnectionHook(store);
    await started();
    const conn = connection(fake);
    const id = cellId("c1");
    const execution = { ...MockExecutions.completed(id), id: "mixed-writes" };
    const line = (seq: number, text: string) => ({
      event: "console",
      data: {
        console: {
          id: `line-${seq}`,
          execution_id: execution.id,
          seq,
          name: "stdout",
          text,
        },
      },
    });
    const rows = () =>
      store.get(cellRuntimeAtom(id)).consoleOutputs.map((row) => row.data);
    await act(async () => conn.open());
    act(() => {
      for (const event of fixtureMessages("notebook-events.sse")) {
        if (event.event === "ready") {
          conn.receive({ event: "execution", data: { execution } });
          conn.receive(line(0, "A"));
          if (mode === "replay") {
            conn.receive(line(1, "C"));
          }
          conn.receive(event);
          break;
        }
        conn.receive(event);
      }
      conn.send({
        op: "callback-output",
        cell_id: id,
        replace: mode === "replay",
        entries: [
          {
            channel: "stdout",
            mimetype: "text/plain",
            data: "B",
            timestamp: 2_000_000_000,
          },
        ],
        after_seq: [0],
      });
      if (mode === "live") {
        conn.receive(line(1, "C"));
      }
    });
    expect(rows()).toEqual(["ABC"]);
    act(() => {
      conn.receive({ event: "console.removed", data: { id: "line-0" } });
      conn.receive({ event: "console.removed", data: { id: "line-1" } });
      conn.receive(line(2, "D"));
    });
    expect(rows()).toEqual(["BD"]);
  },
);

it("replays execution, debugger, and callback output independently", async () => {
  const store = createStore();
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  const conn = connection(fake);
  const id = cellId("c1");
  const execution = { ...MockExecutions.failed(id), id: "failed-cell" };
  const line = {
    id: "line",
    execution_id: execution.id,
    seq: 0,
    name: "stdout",
    text: "before pdb",
  };
  const input = {
    id: "request",
    execution_id: execution.id,
    seq: 1,
    prompt: "secret?",
    password: true,
    status: "answered",
  };
  const afterExecution = Date.parse(MockExecutions.T1) / 1000;
  const session = {
    op: "pdb-output",
    cell_id: id,
    entries: [
      {
        channel: "stdout",
        mimetype: "text/plain",
        data: "pdb reply",
        timestamp: afterExecution + 1,
      },
    ],
    replace: true,
  };
  const runtime = () => store.get(cellRuntimeAtom(id));
  await act(async () => conn.open());
  act(() => {
    for (const frame of fixtureMessages("notebook-events.sse")) {
      if (frame.event === "ready") {
        conn.receive({ event: "execution", data: { execution } });
        conn.receive({ event: "console", data: { console: line } });
        conn.receive({ event: "input", data: { input } });
        conn.receive(frame);
        break;
      }
      conn.receive(frame);
    }
    conn.send({
      op: "kernel-ready",
      resumed: true,
      ui_values: {},
      layout: null,
      app_config: { width: "normal" },
      kiosk: false,
      capabilities: {},
      consumer_capabilities: { edit: true, interact: true },
    });
    conn.send({
      ...session,
      entries: [
        session.entries[0],
        {
          ...session.entries[0],
          data: "next pdb reply",
          timestamp: afterExecution + 3,
        },
      ],
    });
    conn.send({
      ...session,
      op: "callback-output",
      entries: [
        {
          ...session.entries[0],
          data: "callback reply",
          timestamp: afterExecution + 2,
        },
      ],
    });
    conn.send({
      ...session,
      entries: [
        session.entries[0],
        {
          ...session.entries[0],
          data: "next pdb reply",
          timestamp: afterExecution + 3,
        },
      ],
    });
  });
  expect(runtime().consoleOutputs.map((v) => v.data)).toEqual([
    "before pdb",
    "secret?",
    "pdb replycallback replynext pdb reply",
  ]);
  expect(runtime().consoleOutputs[1].response).toBeNull();
  act(() =>
    conn.receive({
      event: "console",
      data: { console: { ...line, text: "replaced" } },
    }),
  );
  expect(runtime().consoleOutputs.map((v) => v.data)).toEqual([
    "replaced",
    "secret?",
    "pdb replycallback replynext pdb reply",
  ]);
  act(() => conn.receive({ event: "console.removed", data: { id: line.id } }));
  await vi.waitFor(() =>
    expect(runtime().consoleOutputs.map((v) => v.data)).toEqual([
      "secret?",
      "pdb replycallback replynext pdb reply",
    ]),
  );
});

it.each([
  "live removal",
  "snapshot without an execution",
  "snapshot with an empty execution",
])("discards the previous execution console on %s", async (transition) => {
  const store = createStore();
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  const conn = connection(fake);
  const cell = cellId("c1");
  const execution = { ...MockExecutions.completed(cell), id: "previous-run" };
  const runtime = () => store.get(cellRuntimeAtom(cell));
  await act(async () => conn.open());
  act(() => {
    conn.ready();
    conn.receive({ event: "execution", data: { execution } });
    conn.receive({
      event: "console",
      data: {
        console: {
          id: "old-line",
          execution_id: execution.id,
          seq: 0,
          name: "stdout",
          text: "previous run",
        },
      },
    });
    conn.send({
      op: "callback-output",
      cell_id: cell,
      entries: [
        {
          channel: "stdout",
          mimetype: "text/plain",
          data: "callback",
          timestamp: 1,
        },
      ],
    });
  });
  expect(runtime().consoleOutputs.map((output) => output.data)).toEqual([
    "callbackprevious run",
  ]);
  act(() => {
    if (transition === "live removal") {
      conn.receive({ event: "execution.removed", data: { id: execution.id } });
      return;
    }
    conn.receive({ event: "reset", data: {} });
    for (const event of fixtureMessages("notebook-events.sse")) {
      if (
        event.event === "ready" &&
        transition === "snapshot with an empty execution"
      ) {
        conn.receive({
          event: "execution",
          data: { execution: { ...execution, id: "replacement" } },
        });
      }
      conn.receive(event);
      if (event.event === "ready") {
        break;
      }
    }
  });
  expect(runtime().consoleOutputs.map((output) => output.data)).toEqual([
    "callback",
  ]);
});

it("clears the private debugger prompt and transcript when editing moves to another tab", async () => {
  const store = createStore();
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  const conn = connection(fake);
  const id = cellId("c1");
  const entry = {
    channel: "stdout",
    mimetype: "text/plain",
    data: "public callback",
    timestamp: 1,
  };
  await act(async () => conn.open());
  act(() => {
    conn.ready();
    conn.send({ op: "callback-output", cell_id: id, entries: [entry] });
    conn.send({
      op: "pdb-output",
      cell_id: id,
      entries: [{ ...entry, data: "private debugger", timestamp: 2 }],
    });
    conn.send({ op: "pdb-input", cell_id: id, input_id: "pending" });
  });
  const rows = () =>
    store.get(cellRuntimeAtom(id)).consoleOutputs.map((row) => row.data);
  expect(rows()?.join("")).toContain("private debugger");
  expect(store.get(pendingPdbInputAtom)?.inputId).toBe("pending");
  act(() =>
    conn.send({
      op: "consumer-capabilities",
      consumer_capabilities: { edit: false, interact: true },
    }),
  );
  expect(rows()).toEqual(["public callback"]);
  act(() => {
    conn.send({ op: "pdb-output", cell_id: id, entries: [entry] });
    conn.send({ op: "callback-output", cell_id: id, entries: [] });
  });
  expect(rows()).toEqual([]);
  expect(
    store.get(notebookAtom).cellLogs.map((log) => log.message),
  ).not.toContain("private debugger");
  expect(store.get(pendingPdbInputAtom)).toBeNull();
});

it("collects exported files from execution outputs and public callback media", async () => {
  const store = createStore();
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  const conn = connection(fake);
  await act(async () => conn.open());
  act(() => conn.ready());
  const id = cellId("c1");
  const file = "/@file/stream-image.png";
  const callbackFile = "/@file/callback-image.png";
  const previousFile = "/@file/previous-callback.png";
  const debuggerFile = "/@file/debugger-image.png";
  const [execution, output] = MockExecutions.shown(id, {
    mimetype: "text/html",
    data: `<img src="${file}">`,
  });
  act(() => {
    conn.receive({ event: "execution", id: "planned", data: { execution } });
    conn.receive({ event: "output", id: "updated", data: { output } });
    const media = (path: string) => ({
      channel: "media",
      mimetype: "text/html",
      data: `<img src="${path}">`,
      timestamp: 1,
    });
    conn.send({
      op: "callback-output",
      cell_id: id,
      entries: [media(previousFile)],
    });
    conn.send({
      op: "callback-output",
      cell_id: id,
      entries: [media(callbackFile)],
      replace: true,
    });
    conn.send({
      op: "pdb-output",
      cell_id: id,
      entries: [media(debuggerFile)],
    });
  });
  expect(VirtualFileTracker.INSTANCE.filenames()).toEqual(
    expect.arrayContaining([file, callbackFile]),
  );
  expect(VirtualFileTracker.INSTANCE.filenames()).not.toContain(debuggerFile);
  expect(VirtualFileTracker.INSTANCE.filenames()).not.toContain(previousFile);
  act(() => conn.send({ op: "remove-ui-elements", cell_id: id }));
  expect(VirtualFileTracker.INSTANCE.filenames()).not.toContain(file);
  expect(VirtualFileTracker.INSTANCE.filenames()).not.toContain(callbackFile);
});

it("opens and closes the debugger prompt on the failed cell", async () => {
  const store = createStore();
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  const conn = connection(fake);
  await act(async () => conn.open());
  const id = cellId("failed");
  act(() => conn.send({ op: "pdb-input", cell_id: id, input_id: "p1" }));
  expect(store.get(pendingPdbInputAtom)).toEqual({ cellId: id, inputId: "p1" });
  act(() => conn.receive({ event: "reset", data: {} }));
  expect(store.get(pendingPdbInputAtom)).toBeNull();
  act(() => conn.send({ op: "pdb-input", cell_id: id, input_id: "p2" }));
  expect(store.get(pendingPdbInputAtom)?.inputId).toBe("p2");
  act(() => conn.send({ op: "pdb-input", cell_id: id, input_id: null }));
  expect(store.get(pendingPdbInputAtom)).toBeNull();
});

it("replaces gutter breakpoints with the session's replayed state", async () => {
  const store = createStore();
  const staleCell = cellId("stale");
  const currentCell = cellId("current");
  store.set(breakpointsAtom, new Map([[staleCell, new Set([1])]]));
  const fake = withTransport();
  vi.mocked(useRuntimeManager).mockReturnValue(makeRuntimeManager());
  renderConnectionHook(store);
  await started();
  const conn = connection(fake);
  await act(async () => conn.open());

  act(() =>
    conn.send({ op: "breakpoints", breakpoints: { [currentCell]: [2, 4] } }),
  );
  expect(store.get(breakpointsAtom)).toEqual(
    new Map([[currentCell, new Set([2, 4])]]),
  );

  act(() => conn.send({ op: "breakpoints", breakpoints: {} }));
  expect(store.get(breakpointsAtom)).toEqual(new Map());
});

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
    act(() => conn.ready());
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
    act(() => conn.ready());
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

    const notebook = fixtureEvents("notebook-events.sse").find(
      (event) => event.event === "notebook",
    );
    if (!notebook) {
      throw new Error("Missing notebook fixture");
    }
    act(() =>
      conn.receive({
        ...notebook,
        data: {
          notebook: { ...notebook.data.notebook, name: "Renamed notebook" },
        },
      }),
    );
    expect(store.get(startupProgressAtom)).toEqual({
      phase: "starting-kernel",
      logs: "Kernel startup output\n",
    });

    // A new connection starts from the next session's authoritative snapshot.
    await act(async () => conn.drop());
    await act(async () => vi.advanceTimersByTime(2000));
    await act(async () => conn.open());
    expect(store.get(startupProgressAtom)).toBeNull();
  });

  it("does not flash a notice when startup finishes within the delay", async () => {
    const { conn, send } = await renderNotice();
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
    act(() => conn.ready());
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
