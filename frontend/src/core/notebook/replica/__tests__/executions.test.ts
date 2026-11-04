/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import * as Protocol from "@marimo-team/client/protocol";
import { executions, itemsInOrder } from "../resources/executions";
import { createNotebookReducer } from "@marimo-team/client";
import { fixtureEvents } from "./fixtures";

const reducer = createNotebookReducer({ executions });
const snapshot = fixtureEvents("notebook-events.sse");
const runCells = fixtureEvents("run-cells.sse");
const inputs = fixtureEvents("inputs.sse");
const time = "2026-10-01T09:30:00Z";

function replay(
  events: readonly Protocol.EventOutput[],
  from = reducer.initial,
) {
  return events.reduce(reducer.reduce, from);
}

const resource = (state: ReturnType<typeof replay>) =>
  state.resources.executions;

/** Build one event as the stream would deliver it. */
const event = (message: unknown) => Protocol.Event.parse(message);

const removed = (kind: string, id: string, cursor: string) =>
  event({ event: `${kind}.removed`, id: cursor, data: { id, time } });

/** How the host retires a cell execution: its items first, then itself. */
const retire = (executionId: string, variableId: string) => [
  removed("variable", variableId, "111"),
  removed("execution", executionId, "112"),
];

const ids = (holder: Parameters<typeof itemsInOrder>[0]) =>
  itemsInOrder(holder).map((item) => item.id);

const EMPTY = { latest: null, completed: null };

describe("executions resource", () => {
  it("describes document cells from the snapshot with scratch work beside them", () => {
    const ready = snapshot.findIndex((item) => item.event === "ready");
    const opening = resource(replay(snapshot.slice(0, ready + 1)));
    expect([...opening.cells.keys()]).toEqual(["c1", "c3", "k7f2"]);
    expect([...opening.cells.values()]).toEqual([EMPTY, EMPTY, EMPTY]);
    const scratch = opening.executions.get("e7");
    expect(scratch?.record.status).toBe("running");
    expect(itemsInOrder(scratch!).map((item) => item.kind)).toEqual([
      "console",
    ]);
    expect(opening.runs.get("run-scratch")?.status).toBe("running");

    const done = resource(replay(snapshot));
    expect(done.executions.get("e7")?.record.status).toBe("completed");
    expect(done.runs.get("run-scratch")?.outcome).toBe("succeeded");
    const released = reducer.reduce(
      replay(snapshot),
      removed("run", "run-scratch", "98"),
    );
    expect(resource(released).runs.has("run-scratch")).toBe(false);
  });

  it("follows a cell's execution from queued to completed", () => {
    const start = replay(snapshot);
    const running = resource(replay(runCells.slice(0, 5), start));
    expect(running.cells.get("c3")?.latest?.record.status).toBe("running");
    expect(running.cells.get("c3")?.completed).toBeNull();
    expect(running.cells.get("k7f2")?.latest?.record.status).toBe("queued");
    expect(running.runs.get("run-cells")?.status).toBe("running");

    const done = resource(replay(runCells, start));
    const c3 = done.cells.get("c3");
    expect(c3?.latest?.record.id).toBe("e12");
    expect(c3?.completed?.record.id).toBe("e12");
    expect(c3?.completed).not.toHaveProperty("variables");
    expect(
      [...done.executions.get("e12")!.variables.values()].map((v) => v.name),
    ).toEqual(["x"]);
    expect(done.cells.get("k7f2")?.completed?.record.depends_on).toEqual({
      x: { execution: "e12", update: 0 },
    });
    expect(done.runs.get("run-cells")?.outcome).toBe("succeeded");
    expect([...done.executions.keys()]).toEqual(["e7", "e12", "e13"]);
  });

  it("keeps a cell's last result while the host replaces it", () => {
    const done = replay(runCells, replay(snapshot));
    const result = resource(done).cells.get("c3")!.completed!;
    const retired = replay(retire("e12", "e12-x"), done);
    expect(resource(retired).executions.has("e12")).toBe(false);
    expect(resource(retired).cells.get("c3")).toEqual({
      latest: null,
      completed: result,
    });

    const again = {
      ...result.record,
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
    expect(resource(queued).cells.get("c3")?.latest?.record.id).toBe("e14");
    expect(resource(queued).cells.get("c3")?.completed).toBe(result);

    const completed = replay(
      [
        event({
          event: "variable",
          id: "114",
          data: {
            variable: {
              id: "e14-x",
              execution_id: "e14",
              name: "x",
              revision: { execution: "e14", update: 0 },
              type: "int",
              preview: "22",
            },
          },
        }),
        event({
          event: "execution",
          id: "115",
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
      ],
      queued,
    );
    const c3 = resource(completed).cells.get("c3");
    expect(c3?.latest?.record.id).toBe("e14");
    expect(c3?.completed?.record.id).toBe("e14");
    expect([...resource(completed).executions.keys()]).toEqual([
      "e7",
      "e13",
      "e14",
    ]);
    expect([
      ...resource(completed).executions.get("e14")!.variables.keys(),
    ]).toEqual(["e14-x"]);
  });

  it("takes later additions into a result but not removals", () => {
    const done = replay(runCells, replay(snapshot));
    const late = {
      id: "o9",
      execution_id: "e12",
      seq: 0,
      name: "stdout",
      text: "late\n",
    };
    const shown = {
      id: "d1",
      execution_id: "e12",
      seq: 1,
      mimetype: "text/plain",
      data: "figure",
    };
    const added = replay(
      [
        event({ event: "console", id: "111", data: { console: late } }),
        event({ event: "display", id: "112", data: { display: shown } }),
      ],
      done,
    );
    expect(ids(resource(added).cells.get("c3")!.completed!)).toEqual([
      "o9",
      "d1",
    ]);
    expect(ids(resource(added).executions.get("e12")!)).toEqual(["o9", "d1"]);

    const cleared = replay(
      [
        removed("display", "d1", "113"),
        removed("console", "o9", "114"),
        removed("variable", "e12-x", "115"),
      ],
      added,
    );
    const c3 = resource(cleared).cells.get("c3")!;
    expect(ids(c3.latest!)).toEqual([]);
    expect(c3.latest?.variables.size).toBe(0);
    expect(ids(c3.completed!)).toEqual(["o9", "d1"]);

    const gone = reducer.reduce(cleared, removed("execution", "e12", "116"));
    expect(resource(gone).cells.get("c3")).toEqual({
      latest: null,
      completed: c3.completed,
    });
  });

  it("drops a cell deleted while its execution runs", () => {
    const start = replay(runCells.slice(0, 5), replay(snapshot));
    const deleted = reducer.reduce(start, removed("cell", "c3", "105"));
    expect(resource(deleted).cells.has("c3")).toBe(false);

    const finished = replay(runCells.slice(5), deleted);
    expect(resource(finished).cells.has("c3")).toBe(false);
    expect(resource(finished).executions.get("e12")?.record.status).toBe(
      "completed",
    );
    expect(resource(finished).cells.get("k7f2")?.completed?.record.id).toBe(
      "e13",
    );

    const removedForGood = replay(retire("e12", "e12-x"), finished);
    expect(resource(removedForGood).executions.has("e12")).toBe(false);
    expect(resource(removedForGood).cells.has("c3")).toBe(false);
  });

  it("adopts a restored result and an execution that precedes its cell", () => {
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
    const ready = snapshot.findIndex((item) => item.event === "ready");
    const opened = resource(
      replay([
        ...snapshot.slice(0, ready),
        event({ event: "execution", id: "94", data: { execution: restored } }),
        ...snapshot.slice(ready),
      ]),
    );
    expect(opened.cells.get("c3")?.latest?.record.id).toBe("e-restored");
    expect(opened.cells.get("c3")?.completed?.record.run_id).toBeNull();

    const early = reducer.reduce(
      replay(snapshot),
      event({
        event: "execution",
        id: "98",
        data: { execution: { ...restored, id: "e-zz", cell_id: "zz" } },
      }),
    );
    expect(resource(early).executions.has("e-zz")).toBe(true);
    expect(resource(early).cells.has("zz")).toBe(false);
    const cell = snapshot.find((item) => item.event === "cell")!.data.cell;
    const described = reducer.reduce(
      early,
      event({ event: "cell", id: "99", data: { cell: { ...cell, id: "zz" } } }),
    );
    expect(resource(described).cells.get("zz")?.latest?.record.id).toBe("e-zz");
    expect(resource(described).cells.get("zz")?.completed?.record.id).toBe(
      "e-zz",
    );
  });

  it("orders items by seq, replaces them by id, and drops orphans", () => {
    const start = replay(snapshot);
    const prompted = resource(replay(inputs.slice(0, -1), start));
    const execution = prompted.executions.get("e-input");
    expect(
      itemsInOrder(execution!).map((item) => [
        item.kind,
        item.id,
        item.kind === "input" ? item.status : item.seq,
      ]),
    ).toEqual([
      ["console", "o-input-0", 0],
      ["input", "i1", "answered"],
      ["console", "o-input-2", 2],
      ["input", "i2", "cancelled"],
    ]);
    expect([...prompted.cells.values()]).toEqual([EMPTY, EMPTY, EMPTY]);
    const gone = resource(replay(inputs, start));
    expect(gone.executions.has("e-input")).toBe(false);
    expect(gone.runs.get("run-input")?.outcome).toBe("interrupted");

    const orphan = reducer.reduce(
      start,
      event({
        event: "console",
        id: "400",
        data: {
          console: {
            id: "o-orphan",
            execution_id: "nope",
            seq: 0,
            name: "stdout",
            text: "",
          },
        },
      }),
    );
    expect(orphan.resources).toBe(start.resources);
  });

  it("clears on reset", () => {
    const done = replay(runCells, replay(snapshot));
    const reset = reducer.reduce(done, { event: "reset", data: {} });
    expect(resource(reset)).toBe(executions.initial);
  });
});
