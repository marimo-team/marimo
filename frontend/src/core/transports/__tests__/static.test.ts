/* Copyright 2026 Marimo. All rights reserved. */

import { createNotebookReducer, NotebookEvents } from "@marimo-team/client";
import * as Protocol from "@marimo-team/client/protocol";
import { afterEach, assert, describe, expect, it, vi } from "vitest";
import type { NotebookBackend } from "../../notebook/replica";
import { document as documentResource } from "../../notebook/replica/resources/document";
import {
  createStaticNotebookBackend,
  emptySnapshot,
  type StaticNotebookSnapshot,
  startWithSnapshot,
} from "../static";
import { fixtureEvents } from "../../notebook/replica/__tests__/fixtures";

function snapshot(): StaticNotebookSnapshot {
  const events = fixtureEvents("notebook-events.sse");
  const notebook = events.find((event) => event.event === "notebook")?.data
    .notebook;
  const document = events.find((event) => event.event === "document")?.data
    .document;
  assert(notebook && document);
  return {
    notebook,
    document,
    cells: events.flatMap((event) =>
      event.event === "cell" ? [event.data.cell] : [],
    ),
  };
}

const streams: NotebookEvents[] = [];
afterEach(async () => {
  const closed = streams.splice(0);
  closed.forEach((stream) => stream.close());
  await Promise.all(closed.map((stream) => stream.closed));
  vi.useRealTimers();
});

/** Collect a stream's events up to and including its next `ready`. */
function untilReady(stream: NotebookEvents): Promise<Protocol.EventOutput[]> {
  const events: Protocol.EventOutput[] = [];
  return new Promise((resolve, reject) => {
    stream.subscribe((event) => {
      events.push(Protocol.Event.parse(event));
      if (event.event === "ready") {
        resolve(events);
      }
    }, reject);
  });
}

/** Open a backend's stream and read until it is ready. */
async function read(
  backend: ReturnType<typeof createStaticNotebookBackend>,
  cursor?: string,
) {
  const stream = new NotebookEvents(backend.transport, { cursor });
  streams.push(stream);
  const events = await untilReady(stream);
  return { stream, events };
}

/** A live backend whose stream sends nothing until `release` is called. */
function silentUntilReleased(backend: NotebookBackend) {
  let release = () => {};
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  const attempts: Array<string | null> = [];
  const silent: NotebookBackend = {
    ...backend,
    transport: async (attempt, handlers) => {
      attempts.push(attempt.cursor);
      await released;
      return backend.transport(attempt, handlers);
    },
  };
  return { backend: silent, release: () => release(), attempts };
}

describe("static notebook backend", () => {
  it("supplies a complete document through the normal event reader and reducer", async () => {
    const source = snapshot();
    const { stream, events } = await read(createStaticNotebookBackend(source));
    const reducer = createNotebookReducer({ document: documentResource });
    const state = events.reduce(reducer.reduce, reducer.initial);
    expect(events.map((event) => event.event)).toEqual([
      "notebook",
      "cell",
      "cell",
      "cell",
      "document",
      "ready",
    ]);
    expect(state.notebook).toEqual({ ...source.notebook, operations: [] });
    expect(state.resources.document.current).toEqual({
      revision: source.document,
      cells: new Map(source.cells.map((cell) => [cell.id, cell])),
    });
    expect(stream.status).toBe("connected");
  });

  it("preserves withheld source and its revision metadata", async () => {
    const source = snapshot();
    const cells = source.cells.map((cell) => ({ ...cell, code: null }));
    const { events } = await read(
      createStaticNotebookBackend({ ...source, cells }),
    );
    expect(
      events
        .filter((event) => event.event === "cell")
        .map((event) => event.data.cell),
    ).toEqual(cells);
    expect(
      events.find((event) => event.event === "document")?.data.document,
    ).toEqual(source.document);
  });

  it("serves an empty document as available", async () => {
    const source = snapshot();
    const document = { ...source.document, order: [] };
    const { events } = await read(
      createStaticNotebookBackend({ ...source, document, cells: [] }),
    );
    const reducer = createNotebookReducer({ document: documentResource });
    expect(
      events.reduce(reducer.reduce, reducer.initial).resources.document.current,
    ).toEqual({
      revision: document,
      cells: new Map(),
    });
  });

  it("keeps independent readers open without polling or reconnecting", async () => {
    vi.useFakeTimers();
    const backend = createStaticNotebookBackend(snapshot());
    const first = await read(backend);
    const second = await read(backend);
    first.stream.close();
    await first.stream.closed;
    await vi.advanceTimersByTimeAsync(60_000);
    expect(second.events).toEqual(first.events);
    expect(second.stream.status).toBe("connected");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("resets a resume cursor before replaying its snapshot", async () => {
    const { events } = await read(
      createStaticNotebookBackend(snapshot()),
      "previous-10",
    );
    expect(events[0]).toEqual({ event: "reset", data: {} });
    expect(events.at(-1)).toEqual({ event: "ready", id: "static", data: {} });
  });

  it.each(["edit", "save"] as const)(
    "rejects direct %s commands",
    async (operation) => {
      const backend = createStaticNotebookBackend(snapshot());
      const client = backend.notebook(snapshot().notebook.id);
      const result =
        operation === "edit" ? await client.edit([]) : await client.save();
      expect(result).toEqual({
        ok: false,
        status: 501,
        problem: {
          type: "tag:marimo.io,2026:host/unsupported-operation",
          title: "Unsupported operation",
          status: 501,
          detail: "Static notebooks do not support mutations",
        },
      });
    },
  );

  it("respects cancellation before opening, during delivery, and for commands", async () => {
    const backend = createStaticNotebookBackend(snapshot());
    const before = new AbortController();
    before.abort();
    const open = vi.fn();
    const message = vi.fn();
    await backend.transport(
      { cursor: null, signal: before.signal },
      { open, message },
    );
    expect(open).not.toHaveBeenCalled();
    expect(message).not.toHaveBeenCalled();
    await expect(
      backend
        .notebook(snapshot().notebook.id)
        .edit([], { signal: before.signal }),
    ).rejects.toBe(before.signal.reason);
    const during = new AbortController();
    message.mockImplementation(() => during.abort());
    await backend.transport(
      { cursor: null, signal: during.signal },
      { open, message },
    );
    expect(message).toHaveBeenCalledOnce();
  });
});

describe("starting from an embedded snapshot", () => {
  it("shows the snapshot until the host answers, then resets into its stream", async () => {
    const embedded = snapshot();
    const live = silentUntilReleased(
      createStaticNotebookBackend(emptySnapshot("live")),
    );
    const reducer = createNotebookReducer({ document: documentResource });

    // The snapshot is published on its own, with the host still silent.
    const { stream, events } = await read(
      startWithSnapshot(embedded, live.backend),
    );
    expect(events.map((event) => event.event)).toEqual([
      "notebook",
      "cell",
      "cell",
      "cell",
      "document",
      "ready",
    ]);
    const shown = events.reduce(reducer.reduce, reducer.initial);
    expect(shown.notebook?.id).toBe(embedded.notebook.id);
    expect(shown.resources.document.current?.cells.size).toBe(3);
    expect(live.attempts).toEqual([null]);

    // The host's first frame discards it, and the host's snapshot follows.
    const host = untilReady(stream);
    live.release();
    const rest = await host;
    expect(rest.map((event) => event.event)).toEqual([
      "reset",
      "notebook",
      "document",
      "ready",
    ]);
    const state = rest.reduce(reducer.reduce, shown);
    expect(state.notebook?.id).toBe("live");
    expect(state.resources.document.current?.cells.size).toBe(0);
    expect(stream.status).toBe("connected");
  });

  it("starts the host connection fresh when resuming from the snapshot's cursor", async () => {
    const embedded = snapshot();
    const live = silentUntilReleased(
      createStaticNotebookBackend(emptySnapshot("live")),
    );
    live.release();
    const { events } = await read(
      startWithSnapshot(embedded, live.backend),
      `${embedded.notebook.id}:snapshot`,
    );
    expect(live.attempts).toEqual([null]);
    expect(events.map((event) => event.event)).toEqual([
      "reset",
      "notebook",
      "document",
      "ready",
    ]);
  });

  it("skips the snapshot when a connection resumes", async () => {
    const backend = startWithSnapshot(
      snapshot(),
      createStaticNotebookBackend(emptySnapshot("live")),
    );
    const { events } = await read(backend, "static");
    expect(events.map((event) => event.event)).toEqual([
      "reset",
      "notebook",
      "document",
      "ready",
    ]);
  });

  it("keeps the live backend's commands", async () => {
    const backend = startWithSnapshot(
      snapshot(),
      createStaticNotebookBackend(emptySnapshot("live")),
    );
    const result = await backend.notebook("live").save();
    expect(result).toMatchObject({ ok: false, status: 501 });
  });
});
