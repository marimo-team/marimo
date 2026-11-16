/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type * as Protocol from "../protocol.ts";
import { createNotebookReducer, type NotebookResource } from "../index.ts";
import { fixtureEvents } from "./fixtures.ts";

interface CellIds {
  readonly ids: readonly string[];
}

/** A resource whose events are complete on their own. */
const cells: NotebookResource<CellIds, "cell"> = {
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
const revisions: NotebookResource<Revisions, "cell" | "document"> = {
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

function createTestReducer() {
  return createNotebookReducer({ cells, revisions });
}

function replay(
  reducer: ReturnType<typeof createTestReducer>,
  events: readonly Protocol.EventOutput[],
  from = reducer.initial,
) {
  return events.reduce((state, event) => reducer.reduce(state, event), from);
}

const snapshot = fixtureEvents("notebook-events.sse");
const ready = snapshot.findIndex((event) => event.event === "ready");
const cellEvent = snapshot.find((event) => event.event === "cell");
if (cellEvent?.event !== "cell") {
  throw new Error("Fixture is missing a cell event");
}

describe("notebook reducer", () => {
  it("reads the snapshot, goes live at ready, and rebuilds after reset", () => {
    const reducer = createTestReducer();
    const partial = replay(reducer, snapshot.slice(0, ready));
    expect(partial).toMatchObject({ phase: "snapshot", notebookId: "n1" });
    expect(partial.resources.cells.ids).toEqual(["c1", "c3", "k7f2"]);
    expect(partial.resources.revisions).toEqual({
      pending: ["c1", "c3", "k7f2"],
      published: [],
    });

    const live = replay(reducer, snapshot.slice(ready), partial);
    expect(live.phase).toBe("live");
    expect(live.resources.cells).toBe(partial.resources.cells);
    expect(live.resources.revisions).toEqual({
      pending: [],
      published: [["c1", "c3", "k7f2"]],
    });

    const resetEvents = fixtureEvents("events-reset.sse");
    const afterReset = reducer.reduce(live, resetEvents[0]);
    expect(afterReset).toEqual(reducer.initial);
    expect(replay(reducer, resetEvents, live).phase).toBe("live");
  });

  it("publishes a live edit group when its document arrives", () => {
    const reducer = createTestReducer();
    const live = replay(reducer, snapshot);
    const [cell, , removed, published] = fixtureEvents("edits.sse");
    const editing = replay(reducer, [cell], live);
    expect(editing.resources.revisions.pending).toEqual(["c2"]);

    const edited = replay(reducer, [removed, published], editing);
    expect(edited.resources.revisions).toEqual({
      pending: [],
      published: [
        ["c1", "c3", "k7f2"],
        ["c2", "k7f2"],
      ],
    });
  });

  it("keeps resource state by reference when an event does not apply", () => {
    const reducer = createTestReducer();
    const state = replay(reducer, snapshot);
    const runtime = snapshot.find((event) => event.event === "runtime");
    expect(reducer.reduce(state, runtime!)).toBe(state);
  });

  it("clears resources when its notebook is removed and ignores other notebooks", () => {
    const reducer = createTestReducer();
    const state = replay(reducer, snapshot);
    const time = "2026-10-01T09:30:00Z";
    expect(
      reducer.reduce(state, {
        event: "notebook.removed",
        id: "100",
        data: { id: "n2", time },
      }),
    ).toBe(state);
    const removed = reducer.reduce(state, {
      event: "notebook.removed",
      id: "100",
      data: { id: "n1", time },
    });
    expect(removed).toMatchObject({
      phase: "live",
      notebookId: "n1",
      notebook: null,
    });
    expect(removed.resources).toBe(reducer.initial.resources);
  });

  it("rejects objects from another notebook", () => {
    const reducer = createTestReducer();
    const state = replay(reducer, snapshot.slice(0, ready));
    const notebook = snapshot[0];
    if (notebook.event !== "notebook") {
      throw new Error("Fixture does not start with its notebook");
    }
    expect(() =>
      reducer.reduce(state, {
        ...notebook,
        data: { notebook: { ...notebook.data.notebook, id: "n2" } },
      }),
    ).toThrow("changed identity");
    expect(() =>
      reducer.reduce(state, {
        ...cellEvent,
        data: { cell: { ...cellEvent.data.cell, notebook_id: "n2" } },
      }),
    ).toThrow("changed identity");
  });

  it("limits handlers to the events of a resource's kinds", () => {
    const documents: NotebookResource<null, "document"> = {
      initial: null,
      on: {
        document: (state) => state,
        ready: (state) => state,
        // @ts-expect-error `cell` is not one of this resource's kinds.
        cell: (state) => state,
      },
    };
    expect(documents.initial).toBeNull();
    // @ts-expect-error The catalog's kinds never reach a notebook stream.
    const hosts: NotebookResource<null, "host"> = { initial: null, on: {} };
    expect(hosts.initial).toBeNull();
  });
});
