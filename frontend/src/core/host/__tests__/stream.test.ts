/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { NotebookEvent } from "../events";
import type { Resource } from "../resources/resource";
import { createStream, type Stream, type StreamState } from "../stream";
import { fixtureEvents } from "./fixtures";

interface CellIds {
  readonly ids: readonly string[];
}

/** A resource that lists cells, to observe how the stream feeds handlers. */
const cells: Resource<CellIds> = {
  initial: { ids: [] },
  on: {
    cell: (state, event) =>
      state.ids.includes(event.data.cell.id)
        ? state
        : { ids: [...state.ids, event.data.cell.id] },
    "cell.removed": (state, event) =>
      state.ids.includes(event.data.id)
        ? { ids: state.ids.filter((id) => id !== event.data.id) }
        : state,
  },
};

type State = StreamState<{ cells: CellIds }>;

function replay(
  stream: Stream<{ cells: CellIds }>,
  events: readonly NotebookEvent[],
  from: State = stream.initial,
): State {
  return events.reduce((state, event) => stream.reduce(state, event), from);
}

const snapshot = fixtureEvents("notebook-events.sse");
const ready = snapshot.findIndex((event) => event.event === "ready");
const cellEvent = snapshot.find((event) => event.event === "cell");
if (cellEvent?.event !== "cell") {
  throw new Error("Fixture is missing a cell event");
}

describe("notebook stream", () => {
  it("reads the snapshot, goes live at ready, and rebuilds after reset", () => {
    const stream = createStream({ cells });
    const partial = replay(stream, snapshot.slice(0, ready));
    expect(partial).toMatchObject({ phase: "snapshot", notebookId: "n1" });
    expect(partial.resources.cells.ids).toEqual(["c1", "c3", "k7f2"]);

    const live = replay(stream, snapshot.slice(ready), partial);
    expect(live.phase).toBe("live");
    expect(live.resources.cells).toBe(partial.resources.cells);

    const resetEvents = fixtureEvents("events-reset.sse");
    const afterReset = stream.reduce(live, resetEvents[0]);
    expect(afterReset).toEqual({ ...stream.initial, notebookId: "n1" });
    expect(replay(stream, resetEvents, live).phase).toBe("live");
  });

  it("returns the same state when no resource changes", () => {
    const stream = createStream({ cells });
    const state = replay(stream, snapshot);
    const runtime = snapshot.find((event) => event.event === "runtime");
    expect(stream.reduce(state, { ...runtime!, id: "100" })).toBe(state);
    expect(
      stream.reduce(state, {
        event: "cell.removed",
        id: "101",
        data: { id: "missing", time: "2026-10-01T09:30:00Z" },
      }),
    ).toBe(state);
    expect(stream.reduce(state, { event: "unknown", name: "x", id: "1" })).toBe(
      state,
    );
    expect(
      stream.reduce(state, { event: "marimo", data: { marimo: {} } }),
    ).toBe(state);
  });

  it("clears resources when its notebook is removed and ignores other notebooks", () => {
    const stream = createStream({ cells });
    const state = replay(stream, snapshot);
    const time = "2026-10-01T09:30:00Z";
    expect(
      stream.reduce(state, {
        event: "notebook.removed",
        id: "100",
        data: { id: "n2", time },
      }),
    ).toBe(state);
    const removed = stream.reduce(state, {
      event: "notebook.removed",
      id: "100",
      data: { id: "n1", time },
    });
    expect(removed).toMatchObject({ phase: "live", notebookId: "n1" });
    expect(removed.resources).toBe(stream.initial.resources);
  });

  it("rejects objects from another notebook", () => {
    const stream = createStream({ cells });
    const state = replay(stream, snapshot.slice(0, ready));
    const notebook = snapshot[0];
    if (notebook.event !== "notebook") {
      throw new Error("Fixture does not start with its notebook");
    }
    expect(() =>
      stream.reduce(state, {
        ...notebook,
        data: { notebook: { ...notebook.data.notebook, id: "n2" } },
      }),
    ).toThrow("changed identity");
    expect(() =>
      stream.reduce(state, {
        ...cellEvent,
        data: { cell: { ...cellEvent.data.cell, notebook_id: "n2" } },
      }),
    ).toThrow("changed identity");
  });

  it("requires a cursor on live events other than reset and notifications", () => {
    const stream = createStream({ cells });
    const state = replay(stream, snapshot);
    expect(() => stream.reduce(state, cellEvent)).toThrow("cursor");
    expect(stream.reduce(state, { ...cellEvent, id: "100" })).toBe(state);
    expect(stream.reduce(state, { event: "reset", data: {} }).phase).toBe(
      "snapshot",
    );
    expect(
      stream.reduce(state, { event: "marimo", data: { marimo: null } }),
    ).toBe(state);
  });
});
