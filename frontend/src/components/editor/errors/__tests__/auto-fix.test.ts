/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { MarimoError } from "@/core/kernel/messages";

const getDatasourceContext = vi.fn<(id: unknown) => string | null>(() => null);

vi.mock("@/core/ai/context/providers/datasource", () => ({
  getDatasourceContext: (id: unknown) => getDatasourceContext(id),
}));

const { buildFixPrompt, buildFixPromptFromText } = await import("../auto-fix");

describe("buildFixPromptFromText", () => {
  beforeEach(() => {
    getDatasourceContext.mockReset();
    getDatasourceContext.mockReturnValue(null);
  });

  it("includes the cell id in the header when provided", () => {
    const prompt = buildFixPromptFromText("boom", cellId("cell-1"));
    expect(prompt).toBe(
      "My cell (id: cell-1) produced the following error. Please fix it:\n\nboom",
    );
  });

  it("uses a generic header when no cell id is provided", () => {
    const prompt = buildFixPromptFromText("boom");
    expect(prompt).toBe(
      "My code gives the following error. Please fix it:\n\nboom",
    );
  });

  it("appends datasource context when available for the cell", () => {
    getDatasourceContext.mockReturnValue("@datasource://my_db");
    const prompt = buildFixPromptFromText("boom", cellId("cell-1"));
    expect(prompt).toBe(
      "My cell (id: cell-1) produced the following error. Please fix it:\n\nboom\n\nDatabase schema: @datasource://my_db",
    );
  });

  it("does not look up datasource context without a cell id", () => {
    buildFixPromptFromText("boom");
    expect(getDatasourceContext).not.toHaveBeenCalled();
  });
});

describe("buildFixPrompt", () => {
  beforeEach(() => {
    getDatasourceContext.mockReset();
    getDatasourceContext.mockReturnValue(null);
  });

  it("uses the error message when present", () => {
    const errors: MarimoError[] = [
      { type: "sql-error", msg: "syntax error", sql_statement: "SELECT" },
    ];
    expect(buildFixPrompt(errors, cellId("cell-1"))).toBe(
      "My cell (id: cell-1) produced the following error. Please fix it:\n\nsyntax error",
    );
  });

  it("joins multiple errors with newlines", () => {
    const errors: MarimoError[] = [
      { type: "syntax", msg: "bad syntax" },
      {
        type: "exception",
        exception_type: "ValueError",
        msg: "bad value",
        raising_cell: null,
      },
    ];
    expect(buildFixPrompt(errors, cellId("cell-1"))).toBe(
      "My cell (id: cell-1) produced the following error. Please fix it:\n\nbad syntax\nbad value",
    );
  });

  it("falls back to the error type when there is no message", () => {
    const errors: MarimoError[] = [
      { type: "multiple-defs", name: "foo", cells: [cellId("foo")] },
    ];
    expect(buildFixPrompt(errors, cellId("cell-1"))).toBe(
      "My cell (id: cell-1) produced the following error. Please fix it:\n\nmultiple-defs",
    );
  });
});
