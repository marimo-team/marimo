/* Copyright 2026 Marimo. All rights reserved. */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ResultRenderer } from "../tool-result";

afterEach(cleanup);

describe("ResultRenderer", () => {
  it.each([
    { status: "success", message: "No output was returned." },
    { status: "success", next_steps: ["Run the edited cells."] },
    {
      status: "success",
      action_url: null,
      next_steps: null,
      meta: null,
      message: "Finished",
    },
    {
      status: "success",
      action_url: "/notebook",
      next_steps: ["Review the output."],
      meta: { source: "notebook" },
      cellsToOutput: { cell: { cellOutput: "Hello", consoleOutput: "" } },
    },
  ])("renders structured results with optional fields: %j", (result) => {
    render(<ResultRenderer result={result} />);

    expect(screen.getByRole("heading", { name: "Tool Result" })).toBeVisible();
    expect(screen.getByText("success")).toBeVisible();
  });

  it("displays messages and tool-specific output without metadata", () => {
    render(
      <ResultRenderer
        result={{
          status: "success",
          message: "Cells finished running.",
          cellsToOutput: { cell: { cellOutput: "Hello", consoleOutput: "" } },
        }}
      />,
    );

    expect(screen.getByText("Cells finished running.")).toBeVisible();
    expect(screen.getByText("cellsToOutput")).toBeVisible();
    expect(screen.getByText(/"cellOutput": "Hello"/)).toBeVisible();
  });

  it("preserves the fallback for unstructured results", () => {
    render(<ResultRenderer result="Plain text result" />);

    expect(screen.queryByRole("heading", { name: "Tool Result" })).toBeNull();
    expect(screen.getByText("Plain text result")).toBeVisible();
  });
});
