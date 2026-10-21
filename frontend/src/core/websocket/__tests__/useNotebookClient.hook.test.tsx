/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NotebookTransport } from "@marimo-team/client";
import { ConnectionState } from "../types";
import { createNotebookTransport } from "../transports/notebook";
import { useNotebookClient } from "../useNotebookClient";
import { fixtureMessages } from "../../host/__tests__/fixtures";
import { agentAttachmentsAtom } from "../../attachments/state";
import { notebookClientAtom } from "../state";

vi.mock("../transports/notebook", () => ({ createNotebookTransport: vi.fn() }));

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

function setup(strict = false) {
  const store = createStore();
  const options = {
    static: false,
    transportType: "websocket" as const,
    url: () => "ws://localhost/ws",
    headers: () => ({}),
    waitUntilReady: async () => undefined,
    checkHealth: async () => true,
    onNotification: vi.fn(),
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
  vi.mocked(createNotebookTransport).mockReset();
});

describe("useNotebookClient", () => {
  it("exposes host presence to the UI without waiting for kernel-ready", async () => {
    const fake = makeTransport();
    vi.mocked(createNotebookTransport).mockReturnValue(fake.transport);
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
    vi.mocked(createNotebookTransport).mockReturnValue(fake.transport);
    const { rerender, options, unmount } = setup();
    await act(async () => Promise.resolve());
    const onNotification = vi.fn();
    rerender({ ...options, onNotification, url: () => "ws://redirected/ws" });
    act(() => fake.notify());
    expect(options.onNotification).not.toHaveBeenCalled();
    expect(onNotification).toHaveBeenCalledExactlyOnceWith({
      data: { op: "reconnected" },
    });
    expect(createNotebookTransport).toHaveBeenCalledOnce();
    const [{ url }] = vi.mocked(createNotebookTransport).mock.calls[0];
    expect(String(await (url as () => Promise<string>)())).toBe(
      "ws://redirected/ws",
    );
    unmount();
  });

  it("closes every stream under Strict Mode and only follows the active lifetime", async () => {
    const fakes: ReturnType<typeof makeTransport>[] = [];
    vi.mocked(createNotebookTransport).mockImplementation(() => {
      const next = makeTransport();
      fakes.push(next);
      return next.transport;
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
