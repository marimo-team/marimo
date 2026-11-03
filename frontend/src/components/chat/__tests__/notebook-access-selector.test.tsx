/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CopilotMode } from "@/core/config/config-schema";
import { NotebookAccessSelector } from "../notebook-access-selector";

Element.prototype.scrollIntoView = vi.fn();

describe("NotebookAccessSelector", () => {
  it("shows legacy Manual as Read only and offers exactly three levels", async () => {
    const onValueChange = vi.fn();
    render(
      <NotebookAccessSelector value="manual" onValueChange={onValueChange} />,
    );

    fireEvent.keyDown(
      screen.getByRole("combobox", { name: "Notebook access: Read only" }),
      { key: "ArrowDown" },
    );
    const options = await screen.findAllByRole("option");
    expect(options.map((option) => option.getAttribute("data-state"))).toEqual([
      "checked",
      "unchecked",
      "unchecked",
    ]);
    expect(options.map((option) => option.textContent)).toEqual([
      "Read onlyRead notebook code, outputs, and variable previews.",
      "Suggest editsRead the notebook and propose cell changes for review.",
      "Full accessRead, edit, and run cells, with Python scratchpad access.",
    ]);
    expect(onValueChange).not.toHaveBeenCalled();
  });

  it.each<{ mode: CopilotMode; label: string }>([
    { mode: "ask", label: "Read only" },
    { mode: "agent", label: "Suggest edits" },
    { mode: "code_mode", label: "Full access" },
  ])("maps $label to the existing $mode setting", async ({ mode, label }) => {
    const onValueChange = vi.fn();
    const { rerender } = render(
      <NotebookAccessSelector value={mode} onValueChange={onValueChange} />,
    );

    expect(
      screen.getByRole("combobox", { name: `Notebook access: ${label}` }),
    ).toHaveTextContent(label);
    expect(onValueChange).not.toHaveBeenCalled();

    rerender(
      <NotebookAccessSelector
        value={mode === "ask" ? "agent" : "ask"}
        onValueChange={onValueChange}
      />,
    );
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "ArrowDown" });
    const option = await screen.findByRole("option", {
      name: new RegExp(`^${label} `),
    });
    fireEvent.keyDown(option, { key: "Enter" });

    expect(onValueChange).toHaveBeenCalledExactlyOnceWith(mode);
  });
});
