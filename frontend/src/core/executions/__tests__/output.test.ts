/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { describe, expect, it } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
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

const HTML: Protocol.DisplayData = { mimetype: "text/html", data: "<b>1</b>" };

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
  records: Protocol.Execution[],
  cleared: CellOutputInputs["cleared"] = new Map(),
  cells: CellOutputInputs["cells"] = new Map(),
): CellOutputInputs {
  const { executions, results } = MockExecutions.inputs(records);
  return { executions, results, cleared, cells };
}

describe("cellOutputView", () => {
  it("shows a value outcome's display as an output", () => {
    const view = cellOutputView(
      inputs([
        MockExecutions.completed(C1, {
          outcome: { kind: "value", display: HTML },
        }),
      ]),
      C1,
    );
    expect(view).toMatchObject({
      channel: "output",
      mimetype: "text/html",
      data: "<b>1</b>",
    });
    expect(view?.timestamp).toBe(Date.parse(MockExecutions.T1) / 1000);
  });

  it("shows nothing for a value that is empty, or a cell without a result", () => {
    const state = inputs([MockExecutions.completed(C1)]);
    expect(cellOutputView(state, C1)).toBeNull();
    expect(cellOutputView(state, C2)).toBeNull();
  });

  it("shows an error outcome as the editor's error output", () => {
    const view = cellOutputView(
      inputs([
        MockExecutions.completed(C1, {
          outcome: {
            kind: "error",
            error: hostError({
              traceback: { mimetype: "text/plain", data: "Traceback..." },
              related: [{ cell_id: C2, range: null, message: "raised" }],
            }),
          },
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
          outcome: {
            kind: "skipped",
            reason: "upstream-stopped",
            message: "An ancestor stopped",
            related: [
              { cell_id: C2, range: null, message: "stopped" },
              { cell_id: C1, range: null, message: "did not run" },
            ],
          },
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

  it("prefers the running execution's value so far over the retained result", () => {
    const previous = MockExecutions.completed(C1, {
      outcome: { kind: "value", display: HTML },
    });
    const running = MockExecutions.running(C1);
    const silent = inputs([previous, running]);
    expect(cellOutputView(silent, C1)?.data).toBe("<b>1</b>");

    const showing = inputs([
      previous,
      {
        ...running,
        outcome: {
          kind: "value",
          display: { mimetype: "text/plain", data: "so far" },
        },
      },
    ]);
    expect(cellOutputView(showing, C1)?.data).toBe("so far");

    const clearedWhileRunning = inputs([
      previous,
      { ...running, outcome: { kind: "value", display: null } },
    ]);
    expect(cellOutputView(clearedWhileRunning, C1)).toBeNull();
  });

  it("names the failed ancestor and the cell it blamed", () => {
    const C3 = cellId("c3");
    const prevented = cellOutputView(
      inputs([
        MockExecutions.completed(C1, {
          outcome: {
            kind: "skipped",
            reason: "upstream-failed",
            message: "An ancestor failed to resolve `x`",
            related: [
              { cell_id: C2, range: null, message: "could not resolve" },
              { cell_id: C3, range: null, message: "expected to define it" },
              { cell_id: C1, range: null, message: "did not run" },
            ],
          },
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
    const ran = MockExecutions.failed(C1, {}, { code_fingerprint: "ran" });
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
    const first = MockExecutions.completed(C1, {
      outcome: { kind: "value", display: HTML },
    });
    const cleared = new Map([[C1, first.id]]);
    expect(cellOutputView(inputs([first], cleared), C1)).toBeNull();

    const second = MockExecutions.completed(C1, {
      outcome: { kind: "value", display: HTML },
    });
    expect(cellOutputView(inputs([second], cleared), C1)).not.toBeNull();
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
    expect(
      cellError(hostError({ kind: "interrupted", name: null, message: "" })),
    ).toEqual({ type: "interruption" });
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
    const done = MockExecutions.completed("scratch", {
      cell_id: null,
      outcome: { kind: "value", display: HTML },
    });
    expect(scratchOutputView(inputs([done]).executions)?.data).toBe("<b>1</b>");

    const running = {
      ...MockExecutions.running("scratch"),
      cell_id: null,
      started_at: MockExecutions.T1,
      outcome: {
        kind: "value" as const,
        display: { mimetype: "text/plain", data: "so far" },
      },
    };
    expect(scratchOutputView(inputs([done, running]).executions)?.data).toBe(
      "so far",
    );
  });
});
