/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NotebookTransport } from "@marimo-team/client";
import { ConnectionState } from "../types";
import { Deferred } from "@/utils/Deferred";
import type { NotebookBackend } from "../../host/backend";
import { createEditorBackend } from "../backend";
import { useNotebookClient } from "../useNotebookClient";
import { fixtureMessages } from "../../host/__tests__/fixtures";
import { agentAttachmentsAtom } from "../../attachments/state";
import { notebookClientAtom } from "../state";

vi.mock("../backend", () => ({ createEditorBackend: vi.fn() }));

/** A backend that follows `transport` and cannot edit. */
function backend(transport: NotebookTransport): NotebookBackend {
  return { transport, notebook: () => ({ edit: vi.fn() }) };
}

/** A transport whose connections the test drives. */
function makeTransport() {
  const opened: {
    signal: AbortSignal;
    open(): void;
    receive(message: unknown): void;
  }[] = [];
  const transport: NotebookTransport = ({ signal }, handlers) =>
    new Promise((resolve) => {
      opened.push({ signal, open: handlers.open, receive: handlers.message });
      signal.addEventListener("abort", () => resolve(), { once: true });
    });
  return {
    transport,
    opened,
    /** Open the latest connection and deliver a host-framed notification. */
    notify: () =>
      opened.at(-1)?.receive({
        event: "marimo",
        data: { marimo: { op: "reconnected" } },
      }),
  };
}

function setup(
  strict = false,
  readiness: {
    waitUntilReady?: () => Promise<void>;
    checkHealth?: () => Promise<boolean>;
  } = {},
) {
  const store = createStore();
  const options = {
    static: false,
    transportType: "websocket" as const,
    url: () => "ws://localhost/ws",
    headers: () => ({}),
    notebookUrl: (id: string) => new URL(`http://localhost/notebooks/${id}`),
    waitUntilReady: async () => undefined,
    checkHealth: async () => true,
    onNotification: vi.fn(),
    ...readiness,
  };
  const wrapper = ({ children }: PropsWithChildren) => (
    <Provider store={store}>{children}</Provider>
  );
  const hook = renderHook((props) => useNotebookClient(props), {
    initialProps: options,
    reactStrictMode: strict,
    wrapper,
  });
  return { ...hook, options, store };
}

beforeEach(() => {
  vi.mocked(createEditorBackend).mockReset();
});

describe("useNotebookClient", () => {
  it.each([true, false])(
    "rechecks health after failed startup (healthy: %s)",
    async (healthy) => {
      const fake = makeTransport();
      vi.mocked(createEditorBackend).mockImplementation(({ url }) =>
        backend(async (attempt, handlers) => {
          if (typeof url === "function") {
            await url();
          }
          if (!attempt.signal.aborted) {
            return fake.transport(attempt, handlers);
          }
        }),
      );
      const waitUntilReady = vi
        .fn()
        .mockRejectedValue(new Error("Startup gave up"));
      const checkHealth = vi.fn().mockResolvedValue(healthy);
      const { result, store, unmount } = setup(false, {
        waitUntilReady,
        checkHealth,
      });
      await act(async () => Promise.resolve());
      expect(store.get(result.current.connectionAtom).state).toBe(
        ConnectionState.CLOSED,
      );

      await act(async () => result.current.reconnect());
      expect({
        healthChecks: checkHealth.mock.calls.length,
        initialWaits: waitUntilReady.mock.calls.length,
        connections: fake.opened.length,
        state: store.get(result.current.connectionAtom).state,
      }).toEqual({
        healthChecks: 1,
        initialWaits: 1,
        connections: healthy ? 1 : 0,
        state: healthy ? ConnectionState.CONNECTING : ConnectionState.CLOSED,
      });
      act(() => fake.opened.at(-1)?.open());
      expect(store.get(result.current.connectionAtom).state).toBe(
        healthy ? ConnectionState.OPEN : ConnectionState.CLOSED,
      );
      unmount();
    },
  );

  it("waits for initial readiness without reviving an unmounted connection", async () => {
    const ready = new Deferred<void>();
    const resolvedUrl = vi.fn();
    vi.mocked(createEditorBackend).mockImplementation(({ url }) =>
      backend(async () => {
        if (typeof url === "function") {
          await url();
          resolvedUrl();
        }
      }),
    );
    const { result, store, unmount } = setup(false, {
      waitUntilReady: () => ready.promise,
    });
    await act(async () => Promise.resolve());
    expect(resolvedUrl).not.toHaveBeenCalled();
    expect(store.get(result.current.connectionAtom)).toEqual({
      state: ConnectionState.CONNECTING,
    });
    unmount();
    await act(async () => ready.resolve());
    expect(store.get(result.current.connectionAtom)).toEqual({
      state: ConnectionState.NOT_STARTED,
    });
    expect(store.get(notebookClientAtom)).toBeNull();
  });

  it("exposes host presence to the UI without waiting for kernel-ready", async () => {
    const fake = makeTransport();
    vi.mocked(createEditorBackend).mockReturnValue(backend(fake.transport));
    const { result, store, unmount } = setup();
    await act(async () => Promise.resolve());
    expect(store.get(notebookClientAtom)).toBe(result.current);
    const [connection] = fake.opened;
    act(() => {
      connection.open();
      fixtureMessages("notebook-events.sse").forEach(connection.receive);
    });
    expect(store.get(agentAttachmentsAtom)).toEqual([
      {
        id: "a2",
        notebook_id: "n1",
        kind: "agent",
        name: "Notebook CLI",
        since: "2026-10-01T09:20:03Z",
      },
    ]);
    unmount();
    expect(store.get(notebookClientAtom)).toBeNull();
    expect(store.get(agentAttachmentsAtom)).toEqual([]);
  });

  it("uses current callbacks and URL providers without reconnecting on a rerender", async () => {
    const fake = makeTransport();
    vi.mocked(createEditorBackend).mockReturnValue(backend(fake.transport));
    const { rerender, options, unmount } = setup();
    await act(async () => Promise.resolve());
    const onNotification = vi.fn();
    rerender({ ...options, onNotification, url: () => "ws://redirected/ws" });
    act(() => fake.notify());
    expect(options.onNotification).not.toHaveBeenCalled();
    expect(onNotification).toHaveBeenCalledExactlyOnceWith({
      data: { op: "reconnected" },
    });
    expect(createEditorBackend).toHaveBeenCalledOnce();
    const [{ url }] = vi.mocked(createEditorBackend).mock.calls[0];
    expect(String(await (url as () => Promise<string>)())).toBe(
      "ws://redirected/ws",
    );
    unmount();
  });

  it("closes every stream under Strict Mode and only follows the active lifetime", async () => {
    const fakes: ReturnType<typeof makeTransport>[] = [];
    vi.mocked(createEditorBackend).mockImplementation(() => {
      const next = makeTransport();
      fakes.push(next);
      return backend(next.transport);
    });
    const { result, store, options, unmount } = setup(true);
    await act(async () => Promise.resolve());
    expect(fakes).toHaveLength(2);
    expect(fakes[0].opened.every((attempt) => attempt.signal.aborted)).toBe(
      true,
    );
    const [active] = fakes[1].opened;
    act(() => active.open());
    expect(store.get(result.current.connectionAtom)).toEqual({
      state: ConnectionState.OPEN,
    });
    act(() => fakes.forEach((fake) => fake.notify()));
    expect(options.onNotification).toHaveBeenCalledOnce();
    unmount();
    expect(active.signal.aborted).toBe(true);
    await result.current.reconnect();
    expect(fakes[1].opened).toHaveLength(1);
  });
});
