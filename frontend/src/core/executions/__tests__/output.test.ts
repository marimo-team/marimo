/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { describe, expect, it } from "vitest";
import { type ExecutionEntries, MockExecutions } from "@/__mocks__/executions";
import { cellId } from "@/__tests__/branded";
import { cell } from "@/core/notebook/document/__tests__/fixtures";
import {
  type CellOutputInputs,
  cellError,
  cellOutputView,
  scratchOutputView,
} from "../output";

const C1 = cellId("c1");
const C2 = cellId("c2");

const HTML: Protocol.Media = { mimetype: "text/html", data: "<b>1</b>" };
/** After every time the execution mocks use. */
const LATER = "2026-10-01T09:30:00Z";

function hostError(overrides: Partial<Protocol.Error>): Protocol.Error {
  return {
    kind: "exception",
    message: "boom",
    source: "marimo",
    severity: "error",
    range: null,
    name: "ValueError",
    traceback: null,
    related: [],
    ...overrides,
  };
}

function inputs(
  records: ExecutionEntries,
  cleared: CellOutputInputs["cleared"] = new Map(),
  cells: CellOutputInputs["cells"] = new Map(),
): CellOutputInputs {
  const { executions, results } = MockExecutions.inputs(records);
  return { executions, results, cleared, cells };
}

describe("cellOutputView", () => {
  it("shows a succeeded execution's output", () => {
    const view = cellOutputView(inputs([MockExecutions.shown(C1, HTML)]), C1);
    expect(view).toMatchObject({
      channel: "output",
      mimetype: "text/html",
      data: "<b>1</b>",
    });
    expect(view?.timestamp).toBe(Date.parse(MockExecutions.T1) / 1000);
  });

  it("shows nothing for an execution without an output, or a cell without a result", () => {
    const state = inputs([MockExecutions.completed(C1)]);
    expect(cellOutputView(state, C1)).toBeNull();
    expect(cellOutputView(state, C2)).toBeNull();
  });

  it("shows an error outcome as the editor's error output", () => {
    const view = cellOutputView(
      inputs([
        MockExecutions.completed(C1, {
          kind: "failed",
          error: hostError({
            traceback: { mimetype: "text/plain", data: "Traceback..." },
            related: [{ cell_id: C2, range: null, message: "Raised it" }],
          }),
        }),
      ]),
      C1,
    );
    expect(view).toMatchObject({
      channel: "marimo-error",
      mimetype: "application/vnd.marimo+error",
      data: [
        {
          type: "exception",
          exception_type: "ValueError",
          msg: "boom",
          raising_cell: C2,
          traceback: "Traceback...",
        },
      ],
    });
  });

  it("shows an interruption and the ancestor notices as the editor does", () => {
    const interrupted = cellOutputView(
      inputs([MockExecutions.interrupted(C1)]),
      C1,
    );
    expect(interrupted?.data).toEqual([{ type: "interruption" }]);

    const stopped = cellOutputView(
      inputs([
        MockExecutions.completed(C1, {
          kind: "skipped",
          reason: "upstream-stopped",
          message: "An ancestor stopped",
          related: [
            { cell_id: C2, range: null, message: "stopped" },
            { cell_id: C1, range: null, message: "did not run" },
          ],
        }),
      ]),
      C1,
    );
    expect(stopped?.data).toEqual([
      {
        type: "ancestor-stopped",
        msg: "An ancestor stopped",
        raising_cell: C2,
      },
    ]);
  });

  it("takes down a did-not-run notice once the cell runs", () => {
    const skipped = MockExecutions.completed(C1, {
      kind: "skipped",
      reason: "upstream-stopped",
      message: "An ancestor stopped",
      related: [{ cell_id: C2, range: null, message: "stopped" }],
    });
    expect(
      cellOutputView(inputs([skipped, MockExecutions.queued(C1)]), C1),
    ).not.toBeNull();
    expect(
      cellOutputView(inputs([skipped, MockExecutions.running(C1)]), C1),
    ).toBeNull();
  });

  it("prefers the running execution's value so far over the retained result", () => {
    const previous = MockExecutions.shown(C1, HTML);
    const running = MockExecutions.running(C1);
    const silent = inputs([previous, running]);
    expect(cellOutputView(silent, C1)?.data).toBe("<b>1</b>");

    const soFar = MockExecutions.output(running, {
      mimetype: "text/plain",
      data: "so far",
    });
    const showing = inputs([previous, running, soFar]);
    expect(cellOutputView(showing, C1)?.data).toBe("so far");

    const clearedWhileRunning = inputs([
      previous,
      running,
      MockExecutions.output(running, null),
    ]);
    expect(cellOutputView(clearedWhileRunning, C1)).toBeNull();
  });

  it("names the failed ancestor and the cell it blamed", () => {
    const C3 = cellId("c3");
    const prevented = cellOutputView(
      inputs([
        MockExecutions.completed(C1, {
          kind: "skipped",
          reason: "upstream-failed",
          message: "An ancestor failed to resolve `x`",
          related: [
            { cell_id: C2, range: null, message: "could not resolve" },
            { cell_id: C3, range: null, message: "expected to define it" },
            { cell_id: C1, range: null, message: "did not run" },
          ],
        }),
      ]),
      C1,
    );
    expect(prevented?.data).toEqual([
      {
        type: "ancestor-prevented",
        msg: "An ancestor failed to resolve `x`",
        raising_cell: C2,
        blamed_cell: C3,
      },
    ]);
  });

  it("carries the source that ran while the confirmed cell still has it", () => {
    const ran = { ...MockExecutions.failed(C1, {}), code_fingerprint: "ran" };
    const same = new Map([
      [C1, cell(C1, "1 / 0", { code_fingerprint: "ran" })],
    ]);
    expect(cellOutputView(inputs([ran], new Map(), same), C1)?.code).toBe(
      "1 / 0",
    );

    const edited = new Map([
      [C1, cell(C1, "1 / 1", { code_fingerprint: "edited" })],
    ]);
    expect(
      cellOutputView(inputs([ran], new Map(), edited), C1)?.code,
    ).toBeUndefined();

    const withheld = new Map([
      [C1, cell(C1, "", { code: null, code_fingerprint: "ran" })],
    ]);
    expect(
      cellOutputView(inputs([ran], new Map(), withheld), C1)?.code,
    ).toBeUndefined();
  });

  it("hides a cleared result until a newer one lands", () => {
    const first = MockExecutions.shown(C1, HTML);
    const cleared = new Map([[C1, { execution: first[0].id, version: 0 }]]);
    expect(cellOutputView(inputs([first], cleared), C1)).toBeNull();

    const second = MockExecutions.shown(C1, HTML);
    expect(cellOutputView(inputs([second], cleared), C1)).not.toBeNull();
  });

  it("keeps a cleared running display hidden when it completes", () => {
    const running = MockExecutions.running(C1);
    const output = MockExecutions.output(running, HTML);
    const cleared = new Map([[C1, { execution: running.id, version: 0 }]]);
    expect(cellOutputView(inputs([running, output], cleared), C1)).toBeNull();

    const finished = { ...MockExecutions.completed(C1), id: running.id };
    expect(cellOutputView(inputs([finished, output], cleared), C1)).toBeNull();
  });
});

describe("cellError", () => {
  it("keeps a syntax error's line and an internal error's name", () => {
    expect(
      cellError(
        hostError({
          kind: "invalid-syntax",
          name: null,
          message: "bad",
          range: {
            start: { line: 2, character: 0 },
            end: { line: 2, character: 0 },
          },
        }),
      ),
    ).toEqual({ type: "syntax", msg: "bad", lineno: 3 });
    expect(
      cellError(hostError({ kind: "internal", name: "abc", message: "oops" })),
    ).toEqual({ type: "unknown", msg: "oops", error_type: "abc" });
  });

  it("shows any other kind as a diagnostic with the cells involved", () => {
    expect(
      cellError(
        hostError({
          kind: "cycle-dependencies",
          name: null,
          message: "This cell is in a cycle",
          related: [
            { cell_id: C2, range: null, message: "reads x from c1" },
            { cell_id: C1, range: null, message: "reads y from c2" },
          ],
        }),
      ),
    ).toEqual({
      type: "diagnostic",
      kind: "cycle-dependencies",
      msg: "This cell is in a cycle",
      related: [
        { cell_id: C2, message: "reads x from c1" },
        { cell_id: C1, message: "reads y from c2" },
      ],
    });
  });
});

describe("scratchOutputView", () => {
  it("shows the latest scratch execution's outcome, or its value so far", () => {
    const done = MockExecutions.shown(null, HTML);
    expect(scratchOutputView(inputs([done]).executions)?.data).toBe("<b>1</b>");

    const running = MockExecutions.execution(null, {
      status: "running",
      started_at: MockExecutions.T1,
    });
    const soFar = MockExecutions.output(running, {
      mimetype: "text/plain",
      data: "so far",
    });
    expect(
      scratchOutputView(inputs([done, running, soFar]).executions)?.data,
    ).toBe("so far");
  });

  it("keeps the previous output until a newer run has one to show", () => {
    const done = MockExecutions.shown(null, HTML);
    const silent = MockExecutions.execution(null, {
      status: "running",
      started_at: LATER,
    });
    expect(scratchOutputView(inputs([done, silent]).executions)?.data).toBe(
      "<b>1</b>",
    );

    // Interrupted before it started, so it has no start time to order by.
    const interrupted = MockExecutions.execution(null, {
      status: "completed",
      started_at: null,
      completed_at: LATER,
      outcome: { kind: "cancelled" },
      depends_on: {},
    });
    expect(
      scratchOutputView(inputs([done, interrupted]).executions)?.data,
    ).toEqual([{ type: "interruption" }]);
  });

  it("shows why a run failed when it has no execution to show", () => {
    const done = MockExecutions.shown(null, HTML);
    const { executions } = inputs([done]);
    const failure = { message: "Kernel channel closed", completedAt: LATER };

    // The run never reached the kernel, so only the run says what happened.
    expect(
      scratchOutputView({
        ...executions,
        scratchFailure: { ...failure, runId: "run-2" },
      })?.data,
    ).toEqual([
      { type: "unknown", msg: "Kernel channel closed", error_type: null },
    ]);

    // Its own execution already shows the error.
    expect(
      scratchOutputView({
        ...executions,
        scratchFailure: { ...failure, runId: done[0].run_id! },
      })?.data,
    ).toBe("<b>1</b>");
  });
});
