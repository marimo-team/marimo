/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, expectTypeOf, it, vi } from "vitest";
import { createCatalogReducer } from "../index.ts";
import { notebooks, projects } from "./catalog-resources.ts";
import {
  CatalogEvents,
  type CatalogEvent,
  type CatalogEventsOptions,
  type Transport,
} from "../index.ts";
import { fixtureEvents } from "./fixtures.ts";

const snapshot = fixtureEvents("events.sse");
const ready = snapshot.findIndex((event) => event.event === "ready");
const record = snapshot.find((event) => event.event === "notebook")!.data
  .notebook;

/** A transport whose last connection stays open until closed by the caller. */
function scripted(...connections: (readonly unknown[])[]) {
  const attempts: (string | null)[] = [];
  const transport: Transport = async (
    { cursor, signal },
    { open, message },
  ) => {
    attempts.push(cursor);
    open();
    const events = connections.shift();
    events?.forEach(message);
    if (connections.length === 0 && !signal.aborted) {
      await new Promise<void>((resolve) =>
        signal.addEventListener("abort", () => resolve(), { once: true }),
      );
    }
  };
  return { transport, attempts };
}

afterEach(() => vi.useRealTimers());

describe("CatalogEvents", () => {
  it("lets a caller wait for the complete snapshot and close the stream", async () => {
    const { transport } = scripted(snapshot);
    const events = new CatalogEvents(transport);
    const reducer = createCatalogReducer({ notebooks, projects });
    let state = reducer.initial;
    for await (const event of events) {
      state = reducer.reduce(state, event);
      if (event.event === "ready") {
        break;
      }
    }
    expect(state.phase).toBe("live");
    expect(state.resources.notebooks).toEqual([record]);
    expect(state.resources.projects.map((project) => project.id)).toEqual([
      "p1",
    ]);
    expect(events.status).toBe("closed");
    await expect(events.closed).resolves.toBeUndefined();
  });

  it("resumes with caller-owned state and applies replay before ready", async () => {
    vi.useFakeTimers();
    const renamed = { ...record, name: "Renamed" };
    const { transport, attempts } = scripted(snapshot.slice(0, ready + 1), [
      { event: "notebook", id: "42", data: { notebook: renamed } },
      { event: "ready", id: "42", data: {} },
    ]);
    const events = new CatalogEvents(transport);
    const reducer = createCatalogReducer({ notebooks });
    let state = reducer.initial;
    events.subscribe((event) => {
      state = reducer.reduce(state, event);
    });
    await vi.advanceTimersByTimeAsync(2000);
    expect(attempts).toEqual([null, "41"]);
    expect(state).toEqual({
      phase: "live",
      resources: { notebooks: [renamed] },
    });
    expect(events.cursor).toBe("42");
    events.close();
  });

  it("discards an interrupted snapshot before reconnecting without a cursor", async () => {
    vi.useFakeTimers();
    const { transport, attempts } = scripted(snapshot.slice(0, ready), [
      { event: "notebook", data: { notebook: { ...record, id: "n2" } } },
      { event: "ready", id: "50", data: {} },
    ]);
    const events = new CatalogEvents(transport);
    const reducer = createCatalogReducer({ notebooks });
    let state = reducer.initial;
    const names: string[] = [];
    events.subscribe((event) => {
      names.push(event.event);
      state = reducer.reduce(state, event);
    });
    await vi.advanceTimersByTimeAsync(2000);
    expect(attempts).toEqual([null, null]);
    expect(names).toEqual([
      "host",
      "project",
      "notebook",
      "runtime",
      "attachment",
      "reset",
      "notebook",
      "ready",
    ]);
    expect(state.resources.notebooks.map((entry) => entry.id)).toEqual(["n2"]);
    events.close();
  });

  it("clears the cursor and caller state when a saved cursor cannot be resumed", async () => {
    const replacement = fixtureEvents("events-reset.sse");
    const { transport, attempts } = scripted(replacement);
    const events = new CatalogEvents(transport, { cursor: "old" });
    const reducer = createCatalogReducer({ notebooks });
    let state = reducer.reduce(reducer.initial, {
      event: "notebook",
      data: { notebook: { ...record, id: "stale" } },
    });
    const cursors: (string | null)[] = [];
    events.subscribe((event) => {
      state = reducer.reduce(state, event);
      cursors.push(events.cursor);
    });
    await vi.waitFor(() => expect(events.cursor).toBe("57"));
    expect(attempts).toEqual(["old"]);
    expect(cursors).toEqual([
      ...replacement.slice(0, -1).map(() => null),
      "57",
    ]);
    expect(state.resources.notebooks.map((entry) => entry.id)).toEqual(["n1"]);
    events.close();
  });

  it("filters catalog kinds while tracking positions of undispatched events", async () => {
    const { transport } = scripted([
      ...snapshot,
      { event: "future", id: "46", data: "unknown" },
    ]);
    const events = new CatalogEvents(transport, { types: ["notebook"] });
    const received: CatalogEvent<"notebook">[] = [];
    events.subscribe((event) => received.push(event));
    await vi.waitFor(() => expect(events.cursor).toBe("46"));
    expect(received.map((event) => event.event)).toEqual([
      "notebook",
      "ready",
      "notebook",
    ]);
    expectTypeOf<CatalogEvent<"notebook">["event"]>().toEqualTypeOf<
      "notebook" | "notebook.removed" | "ready" | "reset"
    >();
    expectTypeOf<CatalogEventsOptions>().not.toHaveProperty("runId");
    expectTypeOf<CatalogEventsOptions["types"]>().toEqualTypeOf<
      | readonly ("host" | "project" | "notebook" | "runtime" | "attachment")[]
      | undefined
    >();
    events.close();
  });

  it("delivers only catalog events by default", async () => {
    const cell = fixtureEvents("notebook-events.sse").find(
      (event) => event.event === "cell",
    )!;
    const { transport } = scripted([
      ...snapshot,
      { ...cell, id: "46" },
      { event: "host.removed", id: "47", data: {} },
    ]);
    const events = new CatalogEvents(transport);
    const received: CatalogEvent[] = [];
    events.subscribe((event) => received.push(event));
    await vi.waitFor(() => expect(events.cursor).toBe("47"));
    expect(received).toEqual(snapshot);
    events.close();
  });

  it("rejects invalid catalog records", async () => {
    const { transport } = scripted([
      { event: "project", data: { project: { id: "p1" } } },
    ]);
    const events = new CatalogEvents(transport);
    await expect(events.closed).rejects.toThrow("invalid project event");
    expect(events.status).toBe("closed");
  });

  it("aborts the transport and closes pending iteration", async () => {
    const controller = new AbortController();
    const { transport } = scripted([]);
    const events = new CatalogEvents(transport, { signal: controller.signal });
    const iterator = events[Symbol.asyncIterator]();
    const next = iterator.next();
    controller.abort();
    await expect(next).resolves.toEqual({ done: true, value: undefined });
    await expect(events.closed).resolves.toBeUndefined();
  });
});
