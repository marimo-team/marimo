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
  events: readonly Protocol.NotebookStreamEventOutput[],
  from = reducer.initial,
) {
  return events.reduce(reducer.reduce, from);
}

const resource = (state: ReturnType<typeof replay>) =>
  state.resources.executions;

/** Build one event as the stream would deliver it. */
const event = (message: unknown) => Protocol.NotebookStreamEvent.parse(message);

const removed = (kind: string, id: string, cursor: string) =>
  event({ event: `${kind}.removed`, id: cursor, data: { id, time } });

/** How the host retires a cell execution: its items first, then itself. */
const retire = (executionId: string, variableId: string) => [
  removed("variable", variableId, "111"),
  removed("execution", executionId, "112"),
];

const ids = (holder: Parameters<typeof itemsInOrder>[0]) =>
  itemsInOrder(holder).map((item) => item.id);

describe("executions resource", () => {
  it("keeps scratch work from the snapshot and completes it after ready", () => {
    const ready = snapshot.findIndex((item) => item.event === "ready");
    const opening = resource(replay(snapshot.slice(0, ready + 1)));
    const scratch = opening.executions.get("e7");
    expect(scratch?.record.state.status).toBe("running");
    expect(itemsInOrder(scratch!).map((item) => item.kind)).toEqual([
      "console",
    ]);
    expect(opening.runs.get("run-scratch")?.state.status).toBe("running");
    expect(opening.latest.size).toBe(0);

    const done = resource(replay(snapshot));
    expect(done.executions.get("e7")?.record.state.status).toBe("completed");
    expect(done.runs.get("run-scratch")?.state).toMatchObject({
      outcome: { kind: "succeeded" },
    });
    const released = reducer.reduce(
      replay(snapshot),
      removed("run", "run-scratch", "98"),
    );
    expect(resource(released).runs.has("run-scratch")).toBe(false);
  });

  it("indexes a cell's execution while it is on the stream", () => {
    const start = replay(snapshot);
    const running = resource(replay(runCells.slice(0, 5), start));
    expect(running.latest.get("c3")).toBe("e12");
    expect(running.executions.get("e12")?.record.state.status).toBe("running");
    expect(running.latest.get("k7f2")).toBe("e13");
    expect(running.runs.get("run-cells")?.state.status).toBe("running");

    const done = replay(runCells, start);
    const e12 = resource(done).executions.get("e12");
    expect(e12?.record.state.status).toBe("completed");
    expect([...e12!.variables.values()].map((v) => v.name)).toEqual(["x"]);
    expect(resource(done).executions.get("e13")?.record.state).toHaveProperty(
      "depends_on",
      {
        x: { execution_id: "e12", update: 0 },
      },
    );
    expect(resource(done).runs.get("run-cells")?.state).toMatchObject({
      outcome: { kind: "succeeded" },
    });

    const retired = replay(retire("e12", "e12-x"), done);
    expect(resource(retired).executions.has("e12")).toBe(false);
    expect(resource(retired).latest.has("c3")).toBe(false);
    const queued = reducer.reduce(
      retired,
      event({
        event: "execution",
        id: "113",
        data: {
          execution: {
            ...e12!.record,
            id: "e14",
            run_id: "run-again",
            status: "queued",
            outcome: null,
            started_at: null,
            completed_at: null,
          },
        },
      }),
    );
    expect(resource(queued).latest.get("c3")).toBe("e14");
    expect([...resource(queued).executions.keys()]).toEqual([
      "e7",
      "e13",
      "e14",
    ]);
  });

  it("applies item and variable removals to the stream's copy", () => {
    const done = replay(runCells, replay(snapshot));
    const late = {
      id: "o9",
      execution_id: "e12",
      seq: 0,
      content: { kind: "text", stream: "stdout", text: "late\n" },
    };
    const shown = {
      id: "d1",
      execution_id: "e12",
      seq: 1,
      content: {
        kind: "media",
        media: { mimetype: "text/plain", data: "figure" },
      },
    };
    const added = replay(
      [
        event({ event: "console", id: "111", data: { console: late } }),
        event({ event: "console", id: "112", data: { console: shown } }),
      ],
      done,
    );
    expect(ids(resource(added).executions.get("e12")!)).toEqual(["o9", "d1"]);

    const cleared = replay(
      [
        removed("console", "d1", "113"),
        removed("console", "o9", "114"),
        removed("variable", "e12-x", "115"),
      ],
      added,
    );
    const e12 = resource(cleared).executions.get("e12")!;
    expect(ids(e12)).toEqual([]);
    expect(e12.variables.size).toBe(0);
    expect(resource(cleared).latest.get("c3")).toBe("e12");
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
    expect(execution!.items.get("i1")?.time).toBe("2026-11-03T14:00:03Z");
    expect(prompted.latest.size).toBe(0);
    const gone = resource(replay(inputs, start));
    expect(gone.executions.has("e-input")).toBe(false);
    expect(gone.runs.get("run-input")?.state).toMatchObject({
      outcome: { kind: "cancelled" },
    });

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
            content: { kind: "text", stream: "stdout", text: "" },
          },
        },
      }),
    );
    expect(orphan.resources).toBe(start.resources);
  });

  it("ignores removals delivered again", () => {
    const retired = replay(
      retire("e12", "e12-x"),
      replay(runCells, replay(snapshot)),
    );
    const again = replay(retire("e12", "e12-x"), retired);
    expect(again.resources).toBe(retired.resources);
  });

  it("clears on reset", () => {
    const done = replay(runCells, replay(snapshot));
    const reset = reducer.reduce(done, { event: "reset", data: {} });
    expect(resource(reset)).toBe(executions.initial);
  });

  it("remembers why the latest scratch run failed until a newer one arrives", () => {
    const run = (
      id: string,
      origin: Protocol.RunOrigin,
      state: Protocol.RunState,
      cursor: string,
    ) =>
      event({
        event: "run",
        id: cursor,
        data: {
          run: {
            id,
            notebook_id: "n1",
            runtime_id: "r1",
            origin,
            created_at: time,
            state,
          },
          time,
        },
      });
    const code: Protocol.RunOrigin = { kind: "code", code: "1" };
    const failed: Protocol.RunState = {
      status: "completed",
      started_at: null,
      completed_at: time,
      outcome: { kind: "failed", message: "Kernel channel closed" },
    };

    const afterFailure = replay(
      [run("run-9", code, failed, "200")],
      replay(snapshot),
    );
    expect(resource(afterFailure).scratchFailure).toEqual({
      runId: "run-9",
      message: "Kernel channel closed",
      completedAt: time,
    });

    // Cell runs say nothing about the scratchpad.
    const afterCells = replay(
      [
        run(
          "run-10",
          { kind: "cells", cell_ids: ["c1"] },
          { status: "queued" },
          "201",
        ),
      ],
      afterFailure,
    );
    expect(resource(afterCells).scratchFailure?.runId).toBe("run-9");

    const afterNext = replay(
      [run("run-11", code, { status: "queued" }, "202")],
      afterCells,
    );
    expect(resource(afterNext).scratchFailure).toBeUndefined();
  });
});
