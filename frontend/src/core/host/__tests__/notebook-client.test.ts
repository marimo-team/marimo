/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest";
import { createStore } from "jotai";
import { ConnectionState } from "../../websocket/types";
import { Deferred } from "@/utils/Deferred";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { classifyCloseEvent } from "../../websocket/connection-state";
import { createNotebookClient } from "../notebook-client";
import { fixtureEvents, fixtureMessages } from "./fixtures";

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

async function open() {
  const url = vi.fn(() => "ws://localhost/ws?session_id=first&cursor=999");
  const setupResult = setup(url);
  const lifetime = new AbortController();
  setupResult.connect(lifetime.signal);
  setupResult.healthy.resolve();
  await setupResult.healthy.promise;
  setupResult.events.dispatchEvent(new Event("open"));
  return { ...setupResult, lifetime, url };
}

describe("NotebookClient attachments", () => {
  const [browser, agent] = fixtureEvents("notebook-events.sse").flatMap(
    (event) => (event.event === "attachment" ? [event.data.attachment] : []),
  );

  it("publishes a complete snapshot and applies live changes independently of kernel readiness", async () => {
    const { client, store, receive, lifetime } = await open();
    const snapshot = fixtureMessages("notebook-events.sse");
    const readyIndex = snapshot.findIndex((event) => event.event === "ready");
    snapshot.slice(0, readyIndex).forEach(receive);
    expect(store.get(client.attachmentsAtom)).toEqual([]);
    snapshot.slice(readyIndex).forEach(receive);
    expect(store.get(client.attachmentsAtom)).toEqual([browser, agent]);
    const renamed = { ...agent, name: "Renamed agent" };
    receive({ event: "attachment", id: "98", data: { attachment: renamed } });
    receive({
      event: "attachment.removed",
      id: "99",
      data: { id: browser.id },
    });
    expect(store.get(client.attachmentsAtom)).toEqual([renamed]);
    receive({ data: { op: "kernel-ready", resumed: false } });
    expect(store.get(client.attachmentsAtom)).toEqual([renamed]);
    receive({ event: "attachment.removed", id: "100", data: { id: agent.id } });
    expect(store.get(client.attachmentsAtom)).toEqual([]);
    lifetime.abort();
  });

  it("resumes attachments alongside an incomplete document and waits for replay ready", async () => {
    const { client, store, receive, events, urls, lifetime } = await open();
    expect(urls[0].searchParams.has("cursor")).toBe(false);
    fixtureMessages("notebook-events.sse").forEach(receive);
    const confirmed = store.get(client.documentAtom);
    const edits = fixtureMessages("edits.sse");
    edits.slice(0, 3).forEach(receive);
    const renamed = { ...agent, name: "Renamed agent" };
    receive({ event: "attachment", id: "112a", data: { attachment: renamed } });
    expect(store.get(client.attachmentsAtom)).toEqual([browser, renamed]);
    events.dispatchEvent(new CloseEvent("close"));
    expect(store.get(client.attachmentsAtom)).toEqual([]);
    expect(urls.at(-1)!.searchParams.get("cursor")).toBe("112a");
    events.dispatchEvent(new Event("open"));
    expect(store.get(client.attachmentsAtom)).toEqual([]);
    expect(store.get(client.documentAtom)).toBe(confirmed);
    edits.slice(3).forEach(receive);
    receive({
      event: "attachment.removed",
      id: "115",
      data: { id: browser.id },
    });
    expect(store.get(client.attachmentsAtom)).toEqual([]);
    receive({ event: "ready", id: "116", data: {} });
    expect(store.get(client.attachmentsAtom)).toEqual([renamed]);
    const revisions = fixtureEvents("edits.sse").flatMap((event) =>
      event.event === "document" ? [event.data.document] : [],
    );
    expect(store.get(client.documentAtom)?.revision).toEqual(revisions.at(-1));
    lifetime.abort();
  });

  it("replaces stale attachments with an empty snapshot after reset", async () => {
    const { client, store, receive, lifetime } = await open();
    fixtureMessages("notebook-events.sse").forEach(receive);
    receive({ event: "reset", data: {} });
    expect(store.get(client.attachmentsAtom)).toEqual([]);
    fixtureMessages("notebook-events.sse")
      .filter((event) => event.event !== "attachment")
      .forEach(receive);
    expect(store.get(client.attachmentsAtom)).toEqual([]);
    lifetime.abort();
  });

  it.each(["close", "error", "malformed", "removed", "abort", "identity"])(
    "clears presence on %s and ignores messages after disposal",
    async (reason) => {
      const { client, store, receive, events, url, lifetime } = await open();
      fixtureMessages("notebook-events.sse").forEach(receive);
      expect(store.get(client.attachmentsAtom)).toEqual([browser, agent]);
      switch (reason) {
        case "close":
          events.dispatchEvent(
            new CloseEvent("close", { reason: "MARIMO_UNAUTHORIZED" }),
          );
          break;
        case "error":
          events.dispatchEvent(new Event("error"));
          break;
        case "malformed":
          receive({ event: "attachment", id: "98", data: {} });
          break;
        case "removed":
          receive({ event: "notebook.removed", id: "98", data: { id: "n1" } });
          break;
        case "identity":
          url.mockReturnValue(
            "ws://localhost/api/marimo/v1/notebooks/n2/events/ws",
          );
          events.dispatchEvent(new CloseEvent("close"));
          receive({ event: "ready", id: "98", data: {} });
          break;
        default:
          lifetime.abort();
      }
      expect(store.get(client.attachmentsAtom)).toEqual([]);
      lifetime.abort();
      fixtureMessages("notebook-events.sse").forEach(receive);
      expect(store.get(client.attachmentsAtom)).toEqual([]);
    },
  );

  it("keeps legacy sessions empty", async () => {
    const { client, store, receive, lifetime } = await open();
    receive({ data: { op: "kernel-ready" } });
    receive({ data: { op: "reconnected" } });
    expect(store.get(client.attachmentsAtom)).toEqual([]);
    lifetime.abort();
  });
});
