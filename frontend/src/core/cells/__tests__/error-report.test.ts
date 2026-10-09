/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { MarimoError } from "@/core/kernel/messages";
import { buildErrorReport, ERROR_HANDOFF_INSTRUCTIONS } from "../error-report";

const CELL_ID = cellId("failed-cell");

describe("buildErrorReport", () => {
  it("owns the instruction to repair the live notebook", () => {
    const report = buildErrorReport(CELL_ID, {
      errors: [{ type: "syntax", msg: "invalid code" }],
    });
    expect(report.output.instructions).toEqual("Fix this notebook error.");
  });

  it("keeps repair intent visible before oversized evidence", () => {
    const report = buildErrorReport(CELL_ID, {
      code: "# long code\n".repeat(10_000),
      errors: [
        {
          type: "exception",
          exception_type: "ValueError",
          msg: "long error ".repeat(10_000),
          raising_cell: null,
          traceback: `<pre>Traceback\n${"long frame\n".repeat(10_000)}</pre>`,
        },
      ],
    });
    const serialized = JSON.stringify(report);

    expect(serialized.length).toBeGreaterThan(8192);
    expect(serialized.slice(0, 256)).toContain(
      '"instructions":"Fix this notebook error."',
    );
  });

  it("retains every message and complete traceback without display limits", () => {
    const traceback = `Traceback\n${"long frame\n".repeat(10_000)}ValueError: bad <value>`;
    const errors: MarimoError[] = [
      {
        type: "exception",
        msg: "bad <value>",
        exception_type: "ValueError",
        raising_cell: null,
        traceback: `<pre>${traceback.replaceAll("<", "&lt;").replaceAll(">", "&gt;")}</pre>`,
      },
      { type: "syntax", msg: "another error" },
    ];
    expect(buildErrorReport(CELL_ID, { code: "failed()", errors })).toEqual({
      type: "cell-output",
      cell_id: CELL_ID,
      code: "failed()",
      output: {
        type: "error",
        instructions: ERROR_HANDOFF_INSTRUCTIONS,
        message: "bad <value>\nanother error",
        traceback,
      },
    });
  });

  it("leaves source unknown for a restored legacy exception", () => {
    expect(
      buildErrorReport(CELL_ID, {
        errors: [
          {
            type: "exception",
            exception_type: "exception",
            msg: "legacy error",
            raising_cell: null,
            traceback: null,
          },
        ],
      }),
    ).toEqual({
      type: "cell-output",
      cell_id: CELL_ID,
      output: {
        type: "error",
        instructions: ERROR_HANDOFF_INSTRUCTIONS,
        message: "legacy error",
      },
    });
  });

  it("preserves empty captured code", () => {
    expect(
      buildErrorReport(CELL_ID, {
        code: "",
        errors: [{ type: "syntax", msg: "invalid code" }],
      }),
    ).toEqual({
      type: "cell-output",
      cell_id: CELL_ID,
      code: "",
      output: {
        type: "error",
        instructions: ERROR_HANDOFF_INSTRUCTIONS,
        message: "invalid code",
      },
    });
  });

  it("keeps separate structured tracebacks in order", () => {
    const errors: MarimoError[] = ["first", "second"].map((message) => ({
      type: "exception",
      exception_type: "ValueError",
      raising_cell: null,
      msg: message,
      traceback: `<pre>Traceback\nValueError: ${message}</pre>`,
    }));
    expect(buildErrorReport(CELL_ID, { errors })).toEqual({
      type: "cell-output",
      cell_id: CELL_ID,
      output: {
        type: "error",
        instructions: ERROR_HANDOFF_INSTRUCTIONS,
        message: "first\nsecond",
        traceback:
          "Traceback\nValueError: first\n\nTraceback\nValueError: second",
      },
    });
  });
});
