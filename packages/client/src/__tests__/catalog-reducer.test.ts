/* Copyright 2026 Marimo. All rights reserved. */

import type { CatalogEvent } from "../index.ts";
import { describe, expect, it } from "vitest";
import { createCatalogReducer, type CatalogResource } from "../index.ts";
import { fixtureEvents } from "./fixtures.ts";
import { notebooks, projects } from "./catalog-resources.ts";

const snapshot = fixtureEvents("events.sse") as CatalogEvent[];
const record = snapshot.find((event) => event.event === "notebook")!.data
  .notebook;
const ready = snapshot.findIndex((event) => event.event === "ready");

describe("catalog reducer", () => {
  it("composes caller resources and discards their state on reset", () => {
    const reducer = createCatalogReducer({ notebooks, projects });
    const partial = snapshot
      .slice(0, ready)
      .reduce(reducer.reduce, reducer.initial);
    expect(partial).toEqual({
      phase: "snapshot",
      resources: {
        notebooks: [record],
        projects: [
          snapshot.find((event) => event.event === "project")!.data.project,
        ],
      },
    });
    const live = snapshot.slice(ready).reduce(reducer.reduce, partial);
    expect(live.phase).toBe("live");
    expect(live.resources.notebooks[0].updated_at).toBe("2026-10-01T09:21:02Z");
    expect(live.resources.projects).toBe(partial.resources.projects);
    const reset = fixtureEvents("events-reset.sse") as CatalogEvent[];
    expect(reducer.reduce(live, reset[0])).toBe(reducer.initial);
    expect(reset.reduce(reducer.reduce, live)).toEqual(live);
    expect(reducer.initial).toEqual({
      phase: "snapshot",
      resources: { notebooks: [], projects: [] },
    });
  });

  it("dispatches notebook records and removals without enforcing one identity", () => {
    const reducer = createCatalogReducer({ notebooks, projects });
    const first = snapshot.reduce(reducer.reduce, reducer.initial);
    const other = { ...record, id: "n2" };
    const both = reducer.reduce(first, {
      event: "notebook",
      data: { notebook: other },
    });
    expect(both.resources.notebooks.map((entry) => entry.id)).toEqual([
      "n1",
      "n2",
    ]);
    const removed = reducer.reduce(both, {
      event: "notebook.removed",
      data: { id: "n1" },
    });
    expect(removed).toEqual({
      phase: "live",
      resources: { notebooks: [other], projects: first.resources.projects },
    });
    expect(first.resources.notebooks).toHaveLength(1);
  });

  it("preserves state when no handler changes it", () => {
    const reducer = createCatalogReducer({ notebooks });
    const state = snapshot.reduce(reducer.reduce, reducer.initial);
    expect(
      reducer.reduce(state, {
        event: "host",
        data: { host: { operations: [] } },
      }),
    ).toBe(state);
    expect(
      reducer.reduce(state, { event: "ready", id: "next", data: {} }),
    ).toBe(state);
  });

  it("passes snapshot and replay phases to resource handlers", () => {
    const phases: CatalogResource<readonly string[], "notebook"> = {
      initial: [],
      on: { ready: (state, _event, context) => [...state, context.phase] },
    };
    const reducer = createCatalogReducer({ phases });
    const readyEvent: CatalogEvent = { event: "ready", id: "1", data: {} };
    const live = reducer.reduce(reducer.initial, readyEvent);
    const resumed = reducer.reduce(live, readyEvent);
    expect(resumed.resources.phases).toEqual(["snapshot", "live"]);
    const reset = reducer.reduce(resumed, { event: "reset", data: {} });
    expect(reducer.reduce(reset, readyEvent)).toEqual(live);
  });
});
