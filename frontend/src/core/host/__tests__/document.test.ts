/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { NotebookEvent } from "../events";
import { document } from "../resources/document";
import { createStream } from "../stream";
import { fixtureEvents } from "./fixtures";

const stream = createStream({ document });
const snapshot = fixtureEvents("notebook-events.sse");
const edits = fixtureEvents("edits.sse");

function replay(events: readonly NotebookEvent[], from = stream.initial) {
  return events.reduce((state, event) => stream.reduce(state, event), from);
}

const confirmed = () => replay(snapshot);
const current = (state: ReturnType<typeof replay>) =>
  state.resources.document.current;

describe("document resource", () => {
  it("publishes the snapshot at ready, then each completed edit and save", () => {
    const ready = snapshot.findIndex((event) => event.event === "ready");
    const opening = replay(snapshot.slice(0, ready));
    expect(current(opening)).toBeNull();
    const first = current(replay(snapshot.slice(ready), opening));
    expect(first?.revision.order).toEqual(["c1", "c3", "k7f2"]);
    expect([...first!.cells.keys()]).toEqual(first?.revision.order);

    const [edit, save] = edits.filter((event) => event.event === "document");
    const pending = replay(
      edits.filter((event) => event.event !== "document"),
      confirmed(),
    );
    expect(current(pending)).toEqual(first);
    const changed = stream.reduce(pending, edit);
    expect(current(changed)?.revision).toEqual(edit.data.document);
    expect([...current(changed)!.cells.keys()].toSorted()).toEqual(
      edit.data.document.order.toSorted(),
    );
    const saved = current(stream.reduce(changed, save));
    expect(saved?.revision).toEqual(save.data.document);
    expect(saved?.cells.get("c3")?.code).toBe("x = 22");
    expect(saved?.cells.has("k7f2")).toBe(false);
    expect(saved?.revision.saved_etag).toBe(saved?.revision.etag);
    expect(first?.cells.get("c3")?.code).toBe("x = 21");
    expect(first?.cells.has("k7f2")).toBe(true);
  });

  it("applies order-only changes and distinguishes an empty notebook from no document", () => {
    const state = confirmed();
    const revision = current(state)!.revision;
    const reordered = {
      ...revision,
      order: revision.order.toReversed(),
      version: revision.version + 1,
    };
    const changed = stream.reduce(state, {
      event: "document",
      data: { document: reordered },
      id: "200",
    });
    expect(current(changed)).toEqual({
      revision: reordered,
      cells: current(state)?.cells,
    });

    const empty = { ...revision, order: [] };
    const opening = stream.reduce(stream.initial, {
      event: "document",
      data: { document: empty },
    });
    expect(current(opening)).toBeNull();
    expect(
      current(stream.reduce(opening, { event: "ready", data: {}, id: "0" })),
    ).toEqual({ revision: empty, cells: new Map() });
    expect(
      current(
        stream.reduce(stream.initial, { event: "ready", data: {}, id: "0" }),
      ),
    ).toBeNull();
  });

  it("keeps the document while a live update is pending and after a replay completes it", () => {
    const state = confirmed();
    const [cell, , removed, published] = edits;
    if (published.event !== "document") {
      throw new Error("Fixture does not publish a document");
    }
    const partial = replay([cell, removed], state);
    expect(current(partial)).toBe(current(state));
    expect(stream.resume(partial)).toBe(partial);
    const completed = replay(
      [published, { event: "ready", data: {}, id: "113" }],
      partial,
    );
    expect(current(completed)?.revision).toEqual(published.data.document);
  });

  it("removes a notebook without waiting for individual cell removals", () => {
    const removed = stream.reduce(confirmed(), {
      event: "notebook.removed",
      data: { id: "n1", time: "2026-10-01T09:30:00Z" },
      id: "200",
    });
    expect(current(removed)).toBeNull();
  });

  it("rejects records that cannot form a complete revision", () => {
    const state = confirmed();
    const revision = current(state)!.revision;
    expect(() =>
      stream.reduce(state, {
        event: "document",
        data: { document: { ...revision, order: ["missing"] } },
        id: "200",
      }),
    ).toThrow("Document records do not match");
    const partial = stream.reduce(state, edits[0]);
    expect(() =>
      stream.reduce(partial, { event: "ready", data: {}, id: "200" }),
    ).toThrow("incomplete document update");
  });
});
