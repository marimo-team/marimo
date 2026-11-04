/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import * as Protocol from "@marimo-team/client/protocol";
import { results } from "../resources/results";
import { createNotebookReducer } from "@marimo-team/client";
import { fixtureEvents } from "./fixtures";

const reducer = createNotebookReducer({ results });
const snapshot = fixtureEvents("notebook-events.sse");
const runCells = fixtureEvents("run-cells.sse");
const time = "2026-10-01T09:30:00Z";

function replay(
  events: readonly Protocol.EventOutput[],
  from = reducer.initial,
) {
  return events.reduce(reducer.reduce, from);
}

const resource = (state: ReturnType<typeof replay>) => state.resources.results;

/** Build one event as the stream would deliver it. */
const event = (message: unknown) => Protocol.Event.parse(message);

const removed = (kind: string, id: string, cursor: string) =>
  event({ event: `${kind}.removed`, id: cursor, data: { id, time } });

/** How the host retires a cell execution: its items first, then itself. */
const retire = (executionId: string, variableId: string) => [
  removed("variable", variableId, "111"),
  removed("execution", executionId, "112"),
];

const restored = {
  id: "e-restored",
  run_id: null,
  runtime_id: null,
  caused_by: null,
  cell_id: "c3",
  code: null,
  code_hash: "0f71456db2ea83f4",
  depends_on: {},
  status: "completed",
  outcome: { kind: "value", display: null },
  started_at: "2026-09-30T09:20:01Z",
  completed_at: "2026-09-30T09:20:02Z",
};

describe("results resource", () => {
  it("has an entry per document cell, filled by a restored result", () => {
    const ready = snapshot.findIndex((item) => item.event === "ready");
    const opening = resource(replay(snapshot.slice(0, ready + 1)));
    expect([...opening]).toEqual([
      ["c1", null],
      ["c3", null],
      ["k7f2", null],
    ]);

    const opened = resource(
      replay([
        ...snapshot.slice(0, ready),
        event({ event: "execution", id: "94", data: { execution: restored } }),
        ...snapshot.slice(ready),
      ]),
    );
    expect(opened.get("c3")?.id).toBe("e-restored");
    expect(opened.get("c3")?.run_id).toBeNull();
  });

  it("records a cell's result when its execution completes", () => {
    const start = replay(snapshot);
    const running = resource(replay(runCells.slice(0, 5), start));
    expect(running.get("c3")).toBeNull();
    expect(running.get("k7f2")).toBeNull();

    const done = resource(replay(runCells, start));
    expect(done.get("c3")?.id).toBe("e12");
    expect(done.get("c3")?.status).toBe("completed");
    expect(done.get("k7f2")?.depends_on).toEqual({
      x: { execution: "e12", update: 0 },
    });
    expect(done.get("c1")).toBeNull();
  });

  it("keeps a result while the host replaces it", () => {
    const done = replay(runCells, replay(snapshot));
    const result = resource(done).get("c3")!;
    const retired = replay(retire("e12", "e12-x"), done);
    expect(resource(retired).get("c3")).toBe(result);

    const again = {
      ...result,
      id: "e14",
      run_id: "run-again",
      status: "queued",
      outcome: null,
      started_at: null,
      completed_at: null,
    };
    const queued = reducer.reduce(
      retired,
      event({ event: "execution", id: "113", data: { execution: again } }),
    );
    expect(resource(queued).get("c3")).toBe(result);

    const completed = reducer.reduce(
      queued,
      event({
        event: "execution",
        id: "114",
        data: {
          execution: {
            ...again,
            status: "completed",
            outcome: { kind: "value", display: null },
            started_at: time,
            completed_at: time,
          },
        },
      }),
    );
    expect(resource(completed).get("c3")?.id).toBe("e14");
  });

  it("replaces a result with an execution interrupted before it started", () => {
    const done = replay(runCells, replay(snapshot));
    const result = resource(done).get("c3")!;
    const interrupted = {
      ...result,
      id: "e14",
      run_id: "run-again",
      status: "completed",
      outcome: { kind: "interrupted" },
      started_at: null,
      completed_at: time,
    };
    const cancelled = replay(
      [
        ...retire("e12", "e12-x"),
        event({
          event: "execution",
          id: "113",
          data: {
            execution: {
              ...interrupted,
              status: "queued",
              outcome: null,
              completed_at: null,
            },
          },
        }),
        event({
          event: "execution",
          id: "114",
          data: { execution: interrupted },
        }),
      ],
      done,
    );
    expect(resource(cancelled).get("c3")?.outcome).toEqual({
      kind: "interrupted",
    });
  });

  it("drops a cell deleted while its execution runs", () => {
    const start = replay(runCells.slice(0, 5), replay(snapshot));
    const deleted = reducer.reduce(start, removed("cell", "c3", "105"));
    expect(resource(deleted).has("c3")).toBe(false);

    const finished = replay(runCells.slice(5), deleted);
    expect(resource(finished).has("c3")).toBe(false);
    expect(resource(finished).get("k7f2")?.id).toBe("e13");
  });

  it("ignores cells it has not seen and clears on reset", () => {
    const start = replay(snapshot);
    const unknown = reducer.reduce(
      start,
      event({
        event: "execution",
        id: "98",
        data: { execution: { ...restored, id: "e-zz", cell_id: "zz" } },
      }),
    );
    expect(unknown.resources).toBe(start.resources);
    const reset = reducer.reduce(replay(runCells, start), {
      event: "reset",
      data: {},
    });
    expect(resource(reset)).toBe(results.initial);
  });
});
