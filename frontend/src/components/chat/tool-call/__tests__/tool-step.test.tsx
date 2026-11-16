/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ToolStep } from "../tool-step";

const edit = { edit: { type: "add_cell", code: "x = 1", position: {} } };

describe("ToolStep", () => {
  it("describes the call and reveals its input and output on demand", () => {
    render(
      <ToolStep
        toolName="tool-edit_notebook_tool"
        state="output-available"
        input={edit}
        result={{ status: "success" }}
      />,
    );
    const row = screen.getByRole("button", { name: /Added cell/ });
    expect(row.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("Tool Request")).toBeNull();

    fireEvent.click(row);
    expect(row.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("Tool Request")).toBeTruthy();
    expect(screen.getByText("Tool Result")).toBeTruthy();
  });

  it("shows the error text of a failed call", () => {
    render(
      <ToolStep
        toolName="lint_notebook"
        state="output-error"
        input={{}}
        errorText="Linter crashed"
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Linted notebook.*Failed/ }),
    );
    expect(screen.getByText("Linter crashed")).toBeTruthy();
  });

  it("marks calls cut off by the end of the turn as stopped", () => {
    render(
      <ToolStep
        toolName="tool-edit_notebook_tool"
        state="input-available"
        input={edit}
        isActive={false}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Adding cell.*Stopped/ }),
    ).toBeTruthy();
  });
});
