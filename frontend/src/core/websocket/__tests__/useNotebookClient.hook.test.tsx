/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectionState } from "../types";
import { createConnectionTransport } from "../transports/create";
import type { IConnectionTransport } from "../transports/transport";
import { useNotebookClient } from "../useNotebookClient";

vi.mock("../transports/create", () => ({ createConnectionTransport: vi.fn() }));

function makeTransport() {
  const events = new EventTarget();
  const transport: IConnectionTransport = {
    readyState: WebSocket.CLOSED,
    reconnect: vi.fn(() => {
      transport.readyState = WebSocket.OPEN;
      events.dispatchEvent(new Event("open"));
    }),
    close: vi.fn(() => {
      transport.readyState = WebSocket.CLOSED;
      events.dispatchEvent(new CloseEvent("close"));
    }),
    send: vi.fn(),
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events),
  };
  return {
    transport,
    notify: () =>
      events.dispatchEvent(
        new MessageEvent("message", {
          data: JSON.stringify({
            event: "marimo",
            data: { marimo: { op: "reconnected" } },
          }),
        }),
      ),
  };
}

function setup(strict = false) {
  const store = createStore();
  const options = {
    sessionId: "first",
    static: false,
    transportType: "websocket" as const,
    messageFormat: "host" as const,
    url: () => "ws://localhost/ws",
    headers: () => ({}),
    waitUntilReady: async () => undefined,
    checkHealth: async () => true,
    onNotification: vi.fn(),
    onMessageError: vi.fn(),
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
  vi.mocked(createConnectionTransport).mockReset();
});

describe("useNotebookClient", () => {
  it("uses current callbacks and URL providers without reconnecting on a rerender", async () => {
    const first = makeTransport();
    vi.mocked(createConnectionTransport).mockReturnValue(first.transport);
    const { rerender, options, unmount } = setup();
    await act(async () => Promise.resolve());
    const onNotification = vi.fn();
    rerender({ ...options, onNotification, url: () => "ws://redirected/ws" });
    act(() => first.notify());
    expect(options.onNotification).not.toHaveBeenCalled();
    expect(onNotification).toHaveBeenCalledExactlyOnceWith({
      data: { op: "reconnected" },
    });
    expect(createConnectionTransport).toHaveBeenCalledOnce();
    expect(vi.mocked(createConnectionTransport).mock.calls[0][0].url()).toBe(
      "ws://redirected/ws",
    );
    unmount();
  });

  it("replaces the transport when session identity changes and ignores old messages", async () => {
    const first = makeTransport();
    const second = makeTransport();
    vi.mocked(createConnectionTransport)
      .mockReturnValueOnce(first.transport)
      .mockReturnValueOnce(second.transport);
    const { rerender, options, unmount } = setup();
    await act(async () => Promise.resolve());
    rerender({ ...options, sessionId: "second" });
    await act(async () => Promise.resolve());
    expect(first.transport.close).toHaveBeenCalledOnce();
    act(() => {
      first.notify();
      second.notify();
    });
    expect(options.onNotification).toHaveBeenCalledOnce();
    unmount();
  });

  it("cleans up every transport under Strict Mode and only connects the active lifetime", async () => {
    const transports: ReturnType<typeof makeTransport>[] = [];
    vi.mocked(createConnectionTransport).mockImplementation(() => {
      const next = makeTransport();
      transports.push(next);
      return next.transport;
    });
    const { result, store, options, unmount } = setup(true);
    await act(async () => Promise.resolve());
    expect(transports).toHaveLength(2);
    expect(transports[0].transport.reconnect).not.toHaveBeenCalled();
    expect(transports[0].transport.close).toHaveBeenCalledOnce();
    expect(transports[1].transport.reconnect).toHaveBeenCalledOnce();
    expect(store.get(result.current.connectionAtom)).toEqual({
      state: ConnectionState.OPEN,
    });
    act(() => {
      for (const transport of transports) {
        transport.notify();
      }
    });
    expect(options.onNotification).toHaveBeenCalledOnce();
    unmount();
    expect(transports[1].transport.close).toHaveBeenCalledOnce();
    await result.current.reconnect();
    expect(transports[1].transport.reconnect).toHaveBeenCalledOnce();
  });
});
