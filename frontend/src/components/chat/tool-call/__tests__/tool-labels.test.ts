/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { describeToolCall } from "../tool-labels";

describe("describeToolCall", () => {
  it("names notebook edits by operation and shows the first line of code", () => {
    const input = {
      edit: {
        type: "add_cell",
        code: "\n  def fib(n):\n    return n",
        position: {},
      },
    };
    expect(
      describeToolCall("tool-edit_notebook_tool", input, "done"),
    ).toMatchObject({
      label: "Added cell",
      detail: "def fib(n):",
    });
    expect(
      describeToolCall("tool-edit_notebook_tool", input, "running").label,
    ).toBe("Adding cell");
  });

  it("falls back to a generic edit label while the input is still streaming", () => {
    expect(
      describeToolCall("tool-edit_notebook_tool", { edit: {} }, "running"),
    ).not.toHaveProperty("detail");
  });

  it("summarizes code-mode runs by their first meaningful line", () => {
    const code =
      "import marimo._code_mode as cm\n# add cells\ncm.add_cell('x = 1')";
    expect(
      describeToolCall("tool-execute_code", { code }, "done"),
    ).toMatchObject({
      label: "Ran code",
      detail: "cm.add_cell('x = 1')",
    });
    expect(
      describeToolCall("execute_code", { code: "import numpy as np" }, "done")
        .detail,
    ).toBe("import numpy as np");
  });

  it("uses plain language for known tools", () => {
    expect(describeToolCall("lint_notebook", {}, "done").label).toBe(
      "Linted notebook",
    );
  });

  it("shows the raw name for unknown tools such as MCP tools", () => {
    expect(describeToolCall("tool-search_docs", {}, "running")).toMatchObject({
      label: "Calling",
      detail: "search_docs",
    });
  });
});
