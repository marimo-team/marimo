/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { MarimoError } from "@/core/kernel/messages";
import { buildErrorReport } from "../error-report";

const CELL_ID = cellId("failed-cell");

describe("buildErrorReport", () => {
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
      output: { type: "error", message: "legacy error" },
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
      output: { type: "error", message: "invalid code" },
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
        message: "first\nsecond",
        traceback:
          "Traceback\nValueError: first\n\nTraceback\nValueError: second",
      },
    });
  });
});
