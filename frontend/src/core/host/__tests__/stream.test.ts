/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { NotebookEvent } from "../events";
import type { Resource } from "../resources/resource";
import { createStream, type Stream, type StreamState } from "../stream";
import { fixtureEvents } from "./fixtures";

interface CellIds {
  readonly ids: readonly string[];
}

/** A resource whose events are complete on their own. */
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

interface Revisions {
  /** Cells changed since the last revision. */
  readonly pending: readonly string[];
  readonly published: readonly (readonly string[])[];
}

function publish(state: Revisions): Revisions {
  return { pending: [], published: [...state.published, state.pending] };
}

/** A resource assembled from groups of events, like a document from its cells. */
const revisions: Resource<Revisions> = {
  initial: { pending: [], published: [] },
  on: {
    cell: (state, event) => ({
      ...state,
      pending: [...state.pending, event.data.cell.id],
    }),
    "cell.removed": (state, event) => ({
      ...state,
      pending: [...state.pending, event.data.id],
    }),
    // A live revision completes a group. A snapshot's revision waits for ready.
    document: (state, _event, { phase }) =>
      phase === "live" ? publish(state) : state,
    ready: publish,
  },
};

interface Resources {
  cells: CellIds;
  revisions: Revisions;
}
type State = StreamState<Resources>;

function replay(
  stream: Stream<Resources>,
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
    const stream = createStream({ cells, revisions });
    const partial = replay(stream, snapshot.slice(0, ready));
    expect(partial).toMatchObject({
      phase: "snapshot",
      notebookId: "n1",
      cursor: null,
    });
    expect(partial.resources.cells.ids).toEqual(["c1", "c3", "k7f2"]);
    expect(partial.resources.revisions).toEqual({
      pending: ["c1", "c3", "k7f2"],
      published: [],
    });

    const live = replay(stream, snapshot.slice(ready), partial);
    expect(live).toMatchObject({ phase: "live", cursor: "97" });
    expect(live.resources.cells).toBe(partial.resources.cells);
    expect(live.resources.revisions).toEqual({
      pending: [],
      published: [["c1", "c3", "k7f2"]],
    });

    const resetEvents = fixtureEvents("events-reset.sse");
    const afterReset = stream.reduce(live, resetEvents[0]);
    expect(afterReset).toEqual({ ...stream.initial, notebookId: "n1" });
    expect(replay(stream, resetEvents, live).phase).toBe("live");
  });

  it("keeps resource state by reference when an event does not apply", () => {
    const stream = createStream({ cells, revisions });
    const state = replay(stream, snapshot);
    const runtime = snapshot.find((event) => event.event === "runtime");
    const unhandled = stream.reduce(state, { ...runtime!, id: "100" });
    expect(unhandled.resources).toBe(state.resources);
    expect(unhandled.cursor).toBe("100");
    expect(
      stream.reduce(state, { event: "unknown", name: "x", id: "101" })
        .resources,
    ).toBe(state.resources);
    expect(
      stream.reduce(state, { event: "marimo", data: { marimo: {} } }),
    ).toBe(state);
  });

  it("clears resources when its notebook is removed and ignores other notebooks", () => {
    const stream = createStream({ cells, revisions });
    const state = replay(stream, snapshot);
    const time = "2026-10-01T09:30:00Z";
    expect(
      stream.reduce(state, {
        event: "notebook.removed",
        id: "100",
        data: { id: "n2", time },
      }).resources,
    ).toBe(state.resources);
    const removed = stream.reduce(state, {
      event: "notebook.removed",
      id: "100",
      data: { id: "n1", time },
    });
    expect(removed).toMatchObject({ phase: "live", notebookId: "n1" });
    expect(removed.resources).toBe(stream.initial.resources);
  });

  it("rejects objects from another notebook", () => {
    const stream = createStream({ cells, revisions });
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

  it("records each live event's cursor and resumes in place", () => {
    const stream = createStream({ cells, revisions });
    const partial = replay(stream, snapshot.slice(0, ready));
    expect(stream.resume(partial)).toEqual({
      ...stream.initial,
      notebookId: "n1",
    });

    const live = replay(stream, snapshot.slice(ready), partial);
    const [cell, , removed, published, saved] = fixtureEvents("edits.sse");
    const editing = replay(stream, [cell], live);
    expect(editing.cursor).toBe("110");
    expect(editing.resources.revisions.pending).toEqual(["c2"]);
    expect(stream.resume(editing)).toBe(editing);

    const edited = replay(stream, [removed, published], editing);
    expect(edited.cursor).toBe("113");
    expect(edited.resources.revisions).toEqual({
      pending: [],
      published: [
        ["c1", "c3", "k7f2"],
        ["c2", "k7f2"],
      ],
    });
    expect(stream.reduce(edited, saved).cursor).toBe("114");
    expect(
      stream.reduce(edited, { event: "ready", id: "116", data: {} }).cursor,
    ).toBe("116");
    expect(stream.reduce(edited, { event: "reset", data: {} }).cursor).toBe(
      null,
    );
  });

  it("requires a cursor on live events other than reset and notifications", () => {
    const stream = createStream({ cells, revisions });
    const state = replay(stream, snapshot);
    expect(() => stream.reduce(state, cellEvent)).toThrow("cursor");
    expect(
      stream.reduce(state, { ...cellEvent, id: "100" }).resources.cells,
    ).toBe(state.resources.cells);
    expect(stream.reduce(state, { event: "reset", data: {} }).phase).toBe(
      "snapshot",
    );
    expect(
      stream.reduce(state, { event: "marimo", data: { marimo: null } }),
    ).toBe(state);
  });
});
