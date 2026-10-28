/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NotebookTransport } from "@marimo-team/client";
import { ConnectionState } from "../types";
import { createEditorBackend } from "../backend";
import { useNotebookReplica } from "../useNotebookReplica";
import { fakeBackend, fixtureMessages } from "../../host/__tests__/fixtures";
import { useNotebookAttachments } from "../../attachments/state";
import { notebookReplicaAtom } from "../state";

vi.mock("../backend", () => ({ createEditorBackend: vi.fn() }));

/** A host-framed native notification. */
const reconnected = {
  event: "marimo",
  data: { marimo: { op: "reconnected" } },
};

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
    notify: () => opened.at(-1)?.receive(reconnected),
  };
}

function setup(strict = false) {
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
  };
  const wrapper = ({ children }: PropsWithChildren) => (
    <Provider store={store}>{children}</Provider>
  );
  const hook = renderHook((props) => useNotebookReplica(props), {
    initialProps: options,
    reactStrictMode: strict,
    wrapper,
  });
  return { ...hook, options, store };
}

beforeEach(() => {
  vi.mocked(createEditorBackend).mockReset();
});

describe("useNotebookReplica", () => {
  it("exposes host presence to the UI without waiting for kernel-ready", async () => {
    const fake = makeTransport();
    vi.mocked(createEditorBackend).mockReturnValue(
      fakeBackend({ transport: fake.transport }),
    );
    const { result, store, unmount } = setup();
    const attachments = renderHook(
      () => ({
        all: useNotebookAttachments(),
        agents: useNotebookAttachments("agent"),
      }),
      {
        wrapper: ({ children }: PropsWithChildren) => (
          <Provider store={store}>{children}</Provider>
        ),
      },
    );
    await act(async () => Promise.resolve());
    expect(store.get(notebookReplicaAtom)).toBe(result.current);
    const [connection] = fake.opened;
    act(() => {
      connection.open();
      fixtureMessages("notebook-events.sse").forEach(connection.receive);
    });
    expect(attachments.result.current.agents).toEqual([
      {
        id: "a2",
        notebook_id: "n1",
        kind: "agent",
        name: "Notebook CLI",
        since: "2026-10-01T09:20:03Z",
      },
    ]);
    expect(attachments.result.current.all).toEqual(
      store.get(result.current.attachmentsAtom),
    );
    expect(attachments.result.current.all.length).toBeGreaterThan(
      attachments.result.current.agents.length,
    );
    unmount();
    expect(store.get(notebookReplicaAtom)).toBeNull();
    expect(attachments.result.current).toEqual({ all: [], agents: [] });
    attachments.unmount();
  });

  it("uses current callbacks and URL providers without reconnecting on a rerender", async () => {
    const fake = makeTransport();
    vi.mocked(createEditorBackend).mockReturnValue(
      fakeBackend({ transport: fake.transport }),
    );
    const { rerender, options, unmount } = setup();
    await act(async () => Promise.resolve());
    const onNotification = vi.fn();
    rerender({ ...options, onNotification, url: () => "ws://redirected/ws" });
    act(() => fake.notify());
    expect(options.onNotification).not.toHaveBeenCalled();
    expect(onNotification).toHaveBeenCalledExactlyOnceWith({
      data: { op: "reconnected" },
    });
    const [{ url }] = vi.mocked(createEditorBackend).mock.calls[0];
    expect(url()).toBe("ws://redirected/ws");
    expect(fake.opened).toHaveLength(1);
    unmount();
  });

  it("follows only the active connection under Strict Mode", async () => {
    const fake = makeTransport();
    vi.mocked(createEditorBackend).mockReturnValue(
      fakeBackend({ transport: fake.transport }),
    );
    const { result, store, options, unmount } = setup(true);
    await act(async () => Promise.resolve());
    const live = fake.opened.filter((attempt) => !attempt.signal.aborted);
    expect(live).toHaveLength(1);
    const [active] = live;
    act(() => active.open());
    expect(store.get(result.current.connectionAtom)).toEqual({
      state: ConnectionState.OPEN,
    });
    act(() => fake.opened.forEach((attempt) => attempt.receive(reconnected)));
    expect(options.onNotification).toHaveBeenCalledOnce();
    unmount();
    expect(active.signal.aborted).toBe(true);
    const attempts = fake.opened.length;
    await result.current.reconnect();
    expect(fake.opened).toHaveLength(attempts);
  });
});
