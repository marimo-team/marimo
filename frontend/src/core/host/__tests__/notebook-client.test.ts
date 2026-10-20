/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest";
import { createStore } from "jotai";
import { ConnectionState } from "../../websocket/types";
import { Deferred } from "@/utils/Deferred";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { classifyCloseEvent } from "../../websocket/connection-state";
import { createNotebookClient } from "../notebook-client";
import { fixtureMessages } from "./fixtures";

function notebookMessage(id: string) {
  const notebook = {
    id,
    project_id: "p1",
    path: null,
    name: id,
    operations: [],
    updated_at: null,
  };
  return JSON.stringify({ event: "notebook", data: { notebook } });
}

function setup(url: () => string = () => "ws://localhost/ws") {
  const events = new EventTarget();
  const healthy = new Deferred<void>();
  let provider = url;
  const urls: URL[] = [];
  const transport = {
    readyState: WebSocket.CLOSED,
    reconnect: vi.fn(() => {
      urls.push(new URL(provider()));
    }),
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
      createTransport: (next) => {
        provider = next;
        return transport;
      },
      url,
      messageFormat: "host",
      signal,
      waitUntilReady: () => healthy.promise,
      checkHealth,
      onNotification: (notification) => onNotification({ data: notification }),
      onMessageError: vi.fn(),
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
    urls,
    receive: (message: unknown) =>
      events.dispatchEvent(
        new MessageEvent("message", { data: JSON.stringify(message) }),
      ),
  };
}

describe("NotebookClient lifetime", () => {
  it.each(["{broken", JSON.stringify({ event: "ready", data: {} })])(
    "stops consuming a malformed host stream: %s",
    (data) => {
      const { connect, events, client, store, transport, onNotification } =
        setup();
      const lifetime = new AbortController();
      connect(lifetime.signal);
      events.dispatchEvent(new Event("open"));
      events.dispatchEvent(new MessageEvent("message", { data }));
      events.dispatchEvent(
        new MessageEvent("message", {
          data: JSON.stringify({
            event: "marimo",
            data: { marimo: { op: "reconnected" } },
          }),
        }),
      );
      expect(store.get(client.connectionAtom)).toEqual({
        state: ConnectionState.CLOSED,
        code: "KERNEL_DISCONNECTED",
        reason: "Failed to decode notebook message",
      });
      expect(transport.close).toHaveBeenCalledOnce();
      expect(onNotification).not.toHaveBeenCalled();
      lifetime.abort();
    },
  );

  it("resumes from the last cursor until reset or a new session", async () => {
    const session = { id: "first", token: "a" };
    const { connect, events, healthy, urls, receive } = setup(
      () =>
        `ws://localhost/ws?session_id=${session.id}&access_token=${session.token}&cursor=999`,
    );
    const lifetime = new AbortController();
    connect(lifetime.signal);
    healthy.resolve();
    await healthy.promise;
    expect(urls[0].searchParams.get("cursor")).toBeNull();

    const snapshot = fixtureMessages("notebook-events.sse");
    events.dispatchEvent(new Event("open"));
    for (const message of snapshot) {
      receive(message);
    }
    session.token = "b";
    events.dispatchEvent(new CloseEvent("close"));
    expect(urls[1].searchParams.get("cursor")).toBe("97");
    expect(urls[1].searchParams.get("access_token")).toBe("b");

    events.dispatchEvent(new Event("open"));
    receive({ event: "reset", data: {} });
    events.dispatchEvent(new CloseEvent("close"));
    expect(urls[2].searchParams.get("cursor")).toBeNull();

    events.dispatchEvent(new Event("open"));
    for (const message of snapshot) {
      receive(message);
    }
    session.id = "second";
    events.dispatchEvent(new CloseEvent("close"));
    expect(urls[3].searchParams.get("cursor")).toBeNull();
    expect(urls[3].searchParams.get("session_id")).toBe("second");
    lifetime.abort();
  });

  it("exposes the confirmed document until the lifetime ends", async () => {
    const { connect, events, client, store, healthy, receive } = setup();
    const lifetime = new AbortController();
    connect(lifetime.signal);
    healthy.resolve();
    await healthy.promise;
    events.dispatchEvent(new Event("open"));
    const snapshot = fixtureMessages("notebook-events.sse");
    for (const message of snapshot.slice(0, -3)) {
      receive(message);
    }
    expect(store.get(client.documentAtom)).toBeNull();
    for (const message of snapshot.slice(-3)) {
      receive(message);
    }
    expect(store.get(client.documentAtom)?.revision.order).toEqual([
      "c1",
      "c3",
      "k7f2",
    ]);
    events.dispatchEvent(new CloseEvent("close"));
    expect(store.get(client.documentAtom)?.revision.order).toEqual([
      "c1",
      "c3",
      "k7f2",
    ]);
    lifetime.abort();
    expect(store.get(client.documentAtom)).toBeNull();
  });

  it("stops consuming a stream whose notebook changes", () => {
    const { connect, events, client, store, transport } = setup();
    const lifetime = new AbortController();
    connect(lifetime.signal);
    events.dispatchEvent(new Event("open"));
    for (const id of ["n1", "n2"]) {
      events.dispatchEvent(
        new MessageEvent("message", { data: notebookMessage(id) }),
      );
    }
    expect(store.get(client.connectionAtom)).toEqual({
      state: ConnectionState.CLOSED,
      code: "KERNEL_DISCONNECTED",
      reason: "Failed to decode notebook message",
    });
    expect(transport.close).toHaveBeenCalledOnce();
    lifetime.abort();
  });

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
