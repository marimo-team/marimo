/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { type NotebookTransport, StreamStopped } from "@marimo-team/client";
import { createStore } from "jotai";
import { afterEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { ConnectionState } from "../../websocket/types";
import type { ConnectionStatus } from "../connection";
import { createNotebookClient } from "../notebook-client";
import {
  type FakeEdit,
  fakeBackend,
  fixtureEvents,
  fixtureMessages,
} from "./fixtures";

/** One connection the fake transport opened. */
interface Attempt {
  readonly cursor: string | null;
  readonly signal: AbortSignal;
  open(): void;
  receive(message: unknown): void;
  /** End the connection so the stream reconnects. */
  drop(): void;
  /** End the stream, with the status the editor shows if the transport has one. */
  stop(status?: ConnectionStatus): void;
}

function setup(edit = vi.fn<FakeEdit>()) {
  const attempts: Attempt[] = [];
  const transport: NotebookTransport = ({ cursor, signal }, handlers) =>
    new Promise((resolve, reject) => {
      attempts.push({
        cursor,
        signal,
        open: handlers.open,
        receive: handlers.message,
        drop: resolve,
        stop: (status) =>
          reject(new StreamStopped("stopped", { cause: status })),
      });
      signal.addEventListener("abort", () => resolve(), { once: true });
    });
  const onNotification = vi.fn();
  const checkHealth = vi.fn(async () => true);
  const store = createStore();
  const backend = fakeBackend({ transport, edit, checkHealth });
  const client = createNotebookClient(store);
  /** Follow the backend until `signal` aborts. */
  const connect = (signal: AbortSignal) => {
    const disconnect = client.connect(backend, {
      onNotification: (notification) => onNotification({ data: notification }),
    });
    signal.addEventListener("abort", disconnect, { once: true });
  };
  let next = 0;
  /** Wait for the next connection, and open it. */
  const opened = async () => {
    await vi.waitFor(() => expect(attempts.length).toBeGreaterThan(next));
    const attempt = attempts[next++];
    attempt.open();
    return attempt;
  };
  return {
    attempts,
    backend,
    client,
    connect,
    onNotification,
    store,
    checkHealth,
    opened,
  };
}

const lifetimes: AbortController[] = [];
function lifetime() {
  const controller = new AbortController();
  lifetimes.push(controller);
  return controller;
}

afterEach(() => {
  lifetimes.splice(0).forEach((controller) => controller.abort());
  vi.useRealTimers();
});

/** Wait out the stream's backoff before it reconnects. */
const backoff = () => vi.advanceTimersByTimeAsync(2000);

const kernelReady = {
  event: "marimo",
  data: { marimo: { op: "kernel-ready", resumed: false } },
};

const notebook = {
  id: "nb/with space",
  project_id: "p1",
  path: null,
  name: "Notebook",
  operations: ["notebook.edit"],
  updated_at: null,
};

describe("NotebookClient lifetime", () => {
  it("ends the previous connection when it connects again", async () => {
    const { attempts, backend, client, opened, store } = setup();
    const first = client.connect(backend, { onNotification: vi.fn() });
    const { receive } = await opened();
    fixtureMessages("notebook-events.sse").forEach(receive);
    const second = client.connect(backend, { onNotification: vi.fn() });
    onTestFinished(second);
    expect(attempts[0].signal.aborted).toBe(true);
    expect(store.get(client.documentAtom)).toBeNull();
    await opened();
    first();
    expect(attempts[1].signal.aborted).toBe(false);
    expect(store.get(client.connectionAtom)).toEqual({
      state: ConnectionState.OPEN,
    });
  });

  it("keeps an edit's target and request identity across a stream reset", async () => {
    const edit = vi.fn<FakeEdit>().mockResolvedValue({
      ok: false,
      status: 409,
      problem: { type: "conflict", title: "conflict", status: 409 },
    });
    const { connect, opened, client } = setup(edit);
    connect(lifetime().signal);
    const { receive } = await opened();
    fixtureMessages("notebook-events.sse").forEach(receive);
    const options = { idempotencyKey: "edit-1", signal: lifetime().signal };
    await client.edit("n1", [], options);
    receive({ event: "reset", data: {} });
    await client.edit("n1", [], options);
    expect(edit.mock.calls).toEqual([
      ["n1", [], options],
      ["n1", [], options],
    ]);

    receive({
      event: "notebook",
      data: { notebook: { ...notebook, id: "n2" } },
    });
    await expect(client.edit("n1", [], options)).rejects.toThrow(
      "notebook changed",
    );
    expect(edit).toHaveBeenCalledTimes(2);
  });

  it("rejects aborted edits and reports edits before connecting", async () => {
    const { client } = setup();
    const controller = lifetime();
    await expect(
      client.edit("n1", [], {
        idempotencyKey: "edit-1",
        signal: controller.signal,
      }),
    ).resolves.toEqual({
      ok: false,
      status: 501,
      problem: {
        type: "tag:marimo.io,2026:host/unsupported-operation",
        title: "Document editing is unavailable on this connection",
        status: 501,
      },
    });
    const reason = new Error("Session ended");
    controller.abort(reason);
    await expect(
      client.edit("n1", [], {
        idempotencyKey: "edit-1",
        signal: controller.signal,
      }),
    ).rejects.toBe(reason);
  });

  it("exposes identity and capabilities only after the notebook is ready", async () => {
    const { connect, opened, client, store } = setup();
    connect(lifetime().signal);
    const { receive } = await opened();
    receive({ event: "notebook", data: { notebook } });
    expect(store.get(client.notebookAtom)).toBeNull();
    receive({ event: "ready", id: "1", data: {} });
    expect(store.get(client.notebookAtom)).toEqual(notebook);
    receive({
      event: "notebook",
      id: "2",
      data: { notebook: { ...notebook, operations: [] } },
    });
    expect(store.get(client.notebookAtom)?.operations).toEqual([]);
    receive({ event: "notebook.removed", id: "3", data: { id: notebook.id } });
    expect(store.get(client.notebookAtom)).toBeNull();
  });

  it("rebuilds the replica after a reconnect reset selects a new notebook", async () => {
    vi.useFakeTimers();
    const { connect, opened, client, store } = setup();
    connect(lifetime().signal);
    const first = await opened();
    fixtureMessages("notebook-events.sse").forEach(first.receive);
    expect(store.get(client.documentAtom)?.revision.notebook_id).toBe("n1");

    first.drop();
    await backoff();
    expect(store.get(client.documentAtom)?.revision.notebook_id).toBe("n1");
    expect(store.get(client.notebookAtom)).toBeNull();
    const second = await opened();
    expect(second.cursor).toBe("97");
    second.receive({ event: "reset", data: {} });
    expect(store.get(client.documentAtom)).toBeNull();
    for (const event of fixtureMessages("notebook-events.sse")) {
      second.receive(
        JSON.parse(JSON.stringify(event).replaceAll('"n1"', '"n2"')),
      );
    }
    expect(store.get(client.documentAtom)?.revision.notebook_id).toBe("n2");
    expect(store.get(client.connectionAtom).state).toBe(ConnectionState.OPEN);
    expect(store.get(client.notebookAtom)?.id).toBe("n2");
  });

  it.each([
    ["a message that is not an event", "{broken"],
    ["an event from another notebook", "identity"],
  ])("stops consuming a stream on %s", async (_name, message) => {
    const { connect, opened, client, store, onNotification } = setup();
    connect(lifetime().signal);
    const attempt = await opened();
    if (message === "identity") {
      attempt.receive({ event: "notebook", data: { notebook } });
      attempt.receive({
        event: "notebook",
        data: { notebook: { ...notebook, id: "n2" } },
      });
    } else {
      attempt.receive(message);
    }
    attempt.receive({
      event: "marimo",
      data: { marimo: { op: "reconnected" } },
    });
    await vi.waitFor(() =>
      expect(store.get(client.connectionAtom).state).toBe(
        ConnectionState.CLOSED,
      ),
    );
    expect(store.get(client.connectionAtom)).toMatchInlineSnapshot(`
      {
        "code": "KERNEL_DISCONNECTED",
        "reason": "Failed to decode notebook message",
        "state": "CLOSED",
      }
    `);
    expect(attempt.signal.aborted).toBe(true);
    expect(onNotification).not.toHaveBeenCalled();
  });

  it("exposes the confirmed document until the lifetime ends", async () => {
    vi.useFakeTimers();
    const { connect, opened, client, store } = setup();
    const current = lifetime();
    connect(current.signal);
    const attempt = await opened();
    const snapshot = fixtureMessages("notebook-events.sse");
    snapshot.slice(0, -3).forEach(attempt.receive);
    expect(store.get(client.documentAtom)).toBeNull();
    snapshot.slice(-3).forEach(attempt.receive);
    expect(store.get(client.documentAtom)?.revision.order).toEqual([
      "c1",
      "c3",
      "k7f2",
    ]);
    attempt.drop();
    await backoff();
    expect(store.get(client.documentAtom)?.revision.order).toEqual([
      "c1",
      "c3",
      "k7f2",
    ]);
    current.abort();
    expect(store.get(client.documentAtom)).toBeNull();
  });

  it.each([
    ["a malformed native envelope", { event: "marimo", id: "98", data: {} }],
    ["null native event data", { event: "marimo", id: "98", data: null }],
    ["an invalid protocol record", { event: "cell", id: "98", data: {} }],
    ["an undecodable message", "{broken"],
    ["a changed notebook", { event: "notebook", id: "98", data: { notebook } }],
  ])(
    "rebuilds from a fresh snapshot after rejecting %s",
    async (_name, message) => {
      const { connect, opened, client, store, onNotification } = setup();
      connect(lifetime().signal);
      const first = await opened();
      const snapshot = fixtureMessages("notebook-events.sse");
      snapshot.forEach(first.receive);
      expect(store.get(client.documentAtom)).not.toBeNull();
      onNotification.mockClear();

      first.receive(message);
      first.receive(kernelReady);
      expect({
        connection: store.get(client.connectionAtom),
        document: store.get(client.documentAtom),
        attachments: store.get(client.attachmentsAtom),
        aborted: first.signal.aborted,
        notifications: onNotification.mock.calls,
      }).toEqual({
        connection: {
          state: ConnectionState.CLOSED,
          code: "KERNEL_DISCONNECTED",
          reason: "Failed to decode notebook message",
        },
        document: null,
        attachments: [],
        aborted: true,
        notifications: [],
      });

      await client.reconnect();
      const second = await opened();
      expect(second.cursor).toBeNull();
      snapshot.forEach(second.receive);
      expect(store.get(client.documentAtom)?.revision.notebook_id).toBe("n1");
      expect(store.get(client.connectionAtom)).toEqual({
        state: ConnectionState.OPEN,
      });
    },
  );

  it.each([
    [
      "a final close",
      {
        state: ConnectionState.CLOSED,
        code: "KERNEL_DISCONNECTED",
        reason: "not authorized",
      },
    ],
    ["the host giving up", undefined],
  ] as const)(
    "shows the stop after %s and resumes on an explicit reconnect",
    async (_name, status) => {
      const { connect, opened, attempts, client, store, checkHealth } = setup();
      connect(lifetime().signal);
      const first = await opened();
      first.receive({ event: "ready", id: "5", data: {} });
      first.stop(status);
      await vi.waitFor(() =>
        expect(store.get(client.connectionAtom)).toEqual(
          status ?? {
            state: ConnectionState.CLOSED,
            code: "KERNEL_DISCONNECTED",
            reason: "kernel not found",
          },
        ),
      );
      expect(attempts).toHaveLength(1);
      await client.reconnect();
      expect(checkHealth).toHaveBeenCalledOnce();
      expect((await opened()).cursor).toBe("5");
    },
  );

  it("does not revive an aborted lifetime when a manual health check finishes", async () => {
    const { connect, opened, attempts, client, checkHealth } = setup();
    const health = new Deferred<boolean>();
    checkHealth.mockReturnValue(health.promise);
    const current = lifetime();
    connect(current.signal);
    const first = await opened();
    first.stop({
      state: ConnectionState.CLOSED,
      code: "KERNEL_DISCONNECTED",
      reason: "",
    });
    await vi.waitFor(() => expect(checkHealth).not.toHaveBeenCalled());
    const attempt = client.reconnect();
    current.abort();
    health.resolve(true);
    await attempt;
    expect(attempts).toHaveLength(1);
  });

  it("discards an interrupted snapshot before a manual reconnect", async () => {
    const { connect, opened, client, store } = setup();
    connect(lifetime().signal);
    const first = await opened();
    const snapshot = fixtureEvents("notebook-events.sse");
    for (const event of snapshot) {
      if (event.event === "ready") {
        break;
      }
      first.receive(event);
    }
    first.stop();
    await vi.waitFor(() =>
      expect(store.get(client.connectionAtom).state).toBe(
        ConnectionState.CLOSED,
      ),
    );

    await client.reconnect();
    const second = await opened();
    expect(second.cursor).toBeNull();
    for (const event of snapshot) {
      if (event.event === "notebook") {
        second.receive(event);
      }
      if (event.event === "document") {
        second.receive({
          ...event,
          data: { document: { ...event.data.document, order: [] } },
        });
      }
    }
    second.receive({ event: "ready", id: "100", data: {} });
    expect({
      connection: store.get(client.connectionAtom),
      order: store.get(client.documentAtom)?.revision.order,
      attachments: store.get(client.attachmentsAtom),
    }).toEqual({
      connection: { state: ConnectionState.OPEN },
      order: [],
      attachments: [],
    });
  });

  it("does not connect after abort", async () => {
    const { connect, attempts, client, store } = setup();
    const current = lifetime();
    connect(current.signal);
    current.abort();
    await client.reconnect();
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(attempts).toHaveLength(0);
    expect(store.get(client.connectionAtom)).toEqual({
      state: ConnectionState.NOT_STARTED,
    });
  });

  it("forwards notifications for the current lifetime only", async () => {
    const { connect, opened, onNotification } = setup();
    const first = lifetime();
    connect(first.signal);
    const earlier = await opened();
    first.abort();
    connect(lifetime().signal);
    const current = await opened();
    earlier.receive(kernelReady);
    current.receive({
      event: "marimo",
      data: { marimo: { op: "reconnected" } },
    });
    expect(onNotification).toHaveBeenCalledExactlyOnceWith({
      data: { op: "reconnected" },
    });
  });
});

describe("NotebookClient attachments", () => {
  const [browser, agent] = fixtureEvents("notebook-events.sse").flatMap(
    (event) => (event.event === "attachment" ? [event.data.attachment] : []),
  );

  async function open() {
    const result = setup();
    result.connect(lifetime().signal);
    return { ...result, attempt: await result.opened() };
  }

  it("publishes a complete snapshot and applies live changes independently of kernel readiness", async () => {
    const { client, store, attempt } = await open();
    const snapshot = fixtureMessages("notebook-events.sse");
    const readyIndex = snapshot.findIndex((event) => event.event === "ready");
    snapshot.slice(0, readyIndex).forEach(attempt.receive);
    expect(store.get(client.attachmentsAtom)).toEqual([]);
    snapshot.slice(readyIndex).forEach(attempt.receive);
    expect(store.get(client.attachmentsAtom)).toEqual([browser, agent]);
    const renamed = { ...agent, name: "Renamed agent" };
    attempt.receive({
      event: "attachment",
      id: "98",
      data: { attachment: renamed },
    });
    attempt.receive({
      event: "attachment.removed",
      id: "99",
      data: { id: browser.id },
    });
    expect(store.get(client.attachmentsAtom)).toEqual([renamed]);
    attempt.receive(kernelReady);
    expect(store.get(client.attachmentsAtom)).toEqual([renamed]);
    attempt.receive({
      event: "attachment.removed",
      id: "100",
      data: { id: agent.id },
    });
    expect(store.get(client.attachmentsAtom)).toEqual([]);
  });

  it.each(["automatic", "manual"])(
    "preserves an incomplete live document across %s reconnect and waits for replay ready",
    async (recovery) => {
      vi.useFakeTimers();
      const { client, store, attempt, opened } = await open();
      expect(attempt.cursor).toBeNull();
      fixtureMessages("notebook-events.sse").forEach(attempt.receive);
      const confirmed = store.get(client.documentAtom);
      const edits = fixtureMessages("edits.sse");
      edits.slice(0, 3).forEach(attempt.receive);
      const renamed = { ...agent, name: "Renamed agent" };
      attempt.receive({
        event: "attachment",
        id: "112a",
        data: { attachment: renamed },
      });
      expect(store.get(client.attachmentsAtom)).toEqual([browser, renamed]);
      if (recovery === "automatic") {
        attempt.drop();
        await backoff();
      } else {
        attempt.stop();
        await vi.advanceTimersByTimeAsync(0);
        await client.reconnect();
      }
      expect(store.get(client.attachmentsAtom)).toEqual([]);
      const replay = await opened();
      expect(replay.cursor).toBe("112a");
      expect(store.get(client.attachmentsAtom)).toEqual([]);
      expect(store.get(client.documentAtom)).toBe(confirmed);
      edits.slice(3).forEach(replay.receive);
      replay.receive({
        event: "attachment.removed",
        id: "115",
        data: { id: browser.id },
      });
      expect(store.get(client.attachmentsAtom)).toEqual([]);
      replay.receive({ event: "ready", id: "116", data: {} });
      expect(store.get(client.attachmentsAtom)).toEqual([renamed]);
      const revisions = fixtureEvents("edits.sse").flatMap((event) =>
        event.event === "document" ? [event.data.document] : [],
      );
      expect(store.get(client.documentAtom)?.revision).toEqual(
        revisions.at(-1),
      );
    },
  );

  it.each(["drop", "stop", "removed", "abort"])(
    "clears presence on %s and ignores messages after disposal",
    async (reason) => {
      vi.useFakeTimers();
      const current = lifetime();
      const result = setup();
      result.connect(current.signal);
      const { client, store } = result;
      const attempt = await result.opened();
      fixtureMessages("notebook-events.sse").forEach(attempt.receive);
      expect(store.get(client.attachmentsAtom)).toEqual([browser, agent]);
      switch (reason) {
        case "drop":
          attempt.drop();
          await backoff();
          break;
        case "stop":
          attempt.stop({
            state: ConnectionState.CLOSED,
            code: "KERNEL_DISCONNECTED",
            reason: "not authorized",
          });
          await vi.advanceTimersByTimeAsync(0);
          break;
        case "removed":
          attempt.receive({
            event: "notebook.removed",
            id: "98",
            data: { id: "n1" },
          });
          break;
        default:
          current.abort();
      }
      expect(store.get(client.attachmentsAtom)).toEqual([]);
      current.abort();
      fixtureMessages("notebook-events.sse").forEach(attempt.receive);
      expect(store.get(client.attachmentsAtom)).toEqual([]);
    },
  );
});
