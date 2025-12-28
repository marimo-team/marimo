/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Debugger } from "../debugger-code";
import { TooltipProvider } from "@/components/ui/tooltip";

// Mock CodeMirror language extensions
vi.mock("@uiw/codemirror-extensions-langs", () => ({
  langs: {
    shell: () => [],
    python: () => [],
  },
}));

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
};

describe("Debugger", () => {
  it("should render debugger output and controls", () => {
    const onSubmit = vi.fn();
    renderWithProvider(<Debugger code="(Pdb) test" onSubmit={onSubmit} />);

    // Check that control buttons are rendered
    expect(screen.getByTestId("debugger-next-button")).toBeInTheDocument();
    expect(screen.getByTestId("debugger-continue-button")).toBeInTheDocument();
    expect(screen.getByTestId("debugger-stack-button")).toBeInTheDocument();
    expect(screen.getByTestId("debugger-help-button")).toBeInTheDocument();
  });

  it("should call onSubmit with 'n' when next button is clicked", () => {
    const onSubmit = vi.fn();
    renderWithProvider(<Debugger code="" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("debugger-next-button"));
    expect(onSubmit).toHaveBeenCalledWith("n");
  });

  it("should call onSubmit with 'c' when continue button is clicked", () => {
    const onSubmit = vi.fn();
    renderWithProvider(<Debugger code="" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("debugger-continue-button"));
    expect(onSubmit).toHaveBeenCalledWith("c");
  });

  it("should call onSubmit with 'bt' when stack button is clicked", () => {
    const onSubmit = vi.fn();
    renderWithProvider(<Debugger code="" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("debugger-stack-button"));
    expect(onSubmit).toHaveBeenCalledWith("bt");
  });

  it("should call onSubmit with 'help' when help button is clicked", () => {
    const onSubmit = vi.fn();
    renderWithProvider(<Debugger code="" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("debugger-help-button"));
    expect(onSubmit).toHaveBeenCalledWith("help");
  });
});
