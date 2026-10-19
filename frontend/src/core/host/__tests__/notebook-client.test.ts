/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest";
import { createStore } from "jotai";
import { ConnectionState } from "../../websocket/types";
import { Deferred } from "@/utils/Deferred";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { classifyCloseEvent } from "../../websocket/connection-state";
import { createNotebookClient } from "../notebook-client";

function setup() {
  const events = new EventTarget();
  const healthy = new Deferred<void>();
  const transport = {
    readyState: WebSocket.CLOSED,
    reconnect: vi.fn(),
    close: vi.fn(() => events.dispatchEvent(new CloseEvent("close"))),
    send: vi.fn(),
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events),
  };
  const onNotification = vi.fn();
  const checkHealth = vi.fn(async () => true);
  const store = createStore();
  const controller = createNotebookClient(store);
  const client = controller.client;
  const connect = (signal: AbortSignal) =>
    controller.connect({
      createTransport: () => transport,
      url: () => "ws://localhost/ws",
      signal,
      waitUntilReady: () => healthy.promise,
      checkHealth,
      onNotification: (notification) => onNotification({ data: notification }),
      decodeJson: jsonParseWithSpecialChar,
      classifyClose: classifyCloseEvent,
    });
  return {
    events,
    healthy,
    transport,
    client,
    connect,
    onNotification,
    store,
    checkHealth,
  };
}

describe("NotebookClient lifetime", () => {
  it.each(["MARIMO_UNAUTHORIZED", "MARIMO_TRANSPORT_EXHAUSTED"])(
    "stops automatic recovery after %s but permits an explicit reconnect",
    async (reason) => {
      const {
        connect,
        client,
        store,
        events,
        transport,
        healthy,
        checkHealth,
      } = setup();
      const lifetime = new AbortController();
      connect(lifetime.signal);
      healthy.resolve();
      await healthy.promise;
      events.dispatchEvent(new CloseEvent("close", { reason }));
      events.dispatchEvent(new Event("error"));
      expect(store.get(client.connectionAtom).state).toBe(
        ConnectionState.CLOSED,
      );
      expect(transport.reconnect).toHaveBeenCalledOnce();
      await client.reconnect();
      expect(checkHealth).toHaveBeenCalledOnce();
      expect(transport.reconnect).toHaveBeenCalledTimes(2);
      lifetime.abort();
    },
  );

  it("only resets the automatic retry budget after an open event", () => {
    const { connect, events, transport } = setup();
    const lifetime = new AbortController();
    connect(lifetime.signal);
    events.dispatchEvent(new CloseEvent("close"));
    events.dispatchEvent(new Event("error"));
    events.dispatchEvent(new CloseEvent("close"));
    expect(transport.reconnect).toHaveBeenCalledOnce();
    events.dispatchEvent(new Event("open"));
    events.dispatchEvent(new CloseEvent("close"));
    expect(transport.reconnect).toHaveBeenCalledTimes(2);
    lifetime.abort();
  });

  it("does not revive an aborted lifetime when a manual health check finishes", async () => {
    const { connect, client, transport, checkHealth } = setup();
    const health = new Deferred<boolean>();
    checkHealth.mockReturnValue(health.promise);
    const lifetime = new AbortController();
    connect(lifetime.signal);
    const attempt = client.reconnect();
    lifetime.abort();
    health.resolve(true);
    await attempt;
    expect(transport.reconnect).not.toHaveBeenCalled();
  });

  it("does not connect after abort, even when the health check finishes", async () => {
    const { client, connect, healthy, transport } = setup();
    const controller = new AbortController();
    connect(controller.signal);
    controller.abort();
    healthy.resolve();
    await healthy.promise;
    client.reconnect();
    expect(transport.reconnect).not.toHaveBeenCalled();
    expect(transport.close).toHaveBeenCalledOnce();
  });

  it("detaches listeners before closing so cleanup cannot trigger a session retry", () => {
    const { connect, client, store, events, transport, onNotification } =
      setup();
    const controller = new AbortController();
    connect(controller.signal);
    controller.abort();
    events.dispatchEvent(
      new MessageEvent("message", {
        data: JSON.stringify({ data: { op: "reconnected" } }),
      }),
    );
    expect(transport.reconnect).not.toHaveBeenCalled();
    expect(store.get(client.connectionAtom)).toEqual({
      state: ConnectionState.NOT_STARTED,
    });
    expect(onNotification).not.toHaveBeenCalled();
  });

  it("can reconnect after effect cleanup without reviving the earlier client attempt", async () => {
    const { connect, healthy, transport, events, onNotification } = setup();
    const first = new AbortController();
    connect(first.signal);
    first.abort();
    const second = new AbortController();
    connect(second.signal);
    healthy.resolve();
    await healthy.promise;
    expect(transport.reconnect).toHaveBeenCalledOnce();
    events.dispatchEvent(
      new MessageEvent("message", {
        data: JSON.stringify({
          event: "marimo",
          data: { marimo: { op: "reconnected" } },
        }),
      }),
    );
    expect(onNotification).toHaveBeenCalledExactlyOnceWith({
      data: { op: "reconnected" },
    });
    second.abort();
  });
});
