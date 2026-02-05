/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useInputHistory } from "@/hooks/useInputHistory";
import { Debugger } from "../debugger-code";

// Mock CodeMirror language extensions
vi.mock("@uiw/codemirror-extensions-langs", () => ({
  langs: {
    sh: () => [],
    py: () => [],
  },
}));

// Mock useInputHistory hook
vi.mock("@/hooks/useInputHistory");

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
};

// Default mock implementation
const mockNavigateUp = vi.fn();
const mockNavigateDown = vi.fn();
const mockAddToHistory = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  (useInputHistory as Mock).mockReturnValue({
    history: [],
    navigateUp: mockNavigateUp,
    navigateDown: mockNavigateDown,
    addToHistory: mockAddToHistory,
  });
});

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

describe("Debugger command history integration", () => {
  it("should initialize useInputHistory hook with correct props", () => {
    const onSubmit = vi.fn();
    renderWithProvider(<Debugger code="" onSubmit={onSubmit} />);

    expect(useInputHistory).toHaveBeenCalled();
    const calls = (useInputHistory as Mock).mock.calls;
    expect(calls.length).toBeGreaterThan(0);

    // Verify hook is called with value and setValue
    const lastCall = calls[calls.length - 1][0];
    expect(lastCall).toHaveProperty("value");
    expect(lastCall).toHaveProperty("setValue");
    expect(typeof lastCall.setValue).toBe("function");
  });

  it("should call navigateUp when ArrowUp is pressed in input area", () => {
    const onSubmit = vi.fn();
    const { container } = renderWithProvider(
      <Debugger code="" onSubmit={onSubmit} />,
    );

    // Find the debugger input wrapper div (parent of CodeMirror)
    const inputWrapper =
      container.querySelector(".debugger-input")?.parentElement;
    expect(inputWrapper).toBeTruthy();

    fireEvent.keyDown(inputWrapper!, { key: "ArrowUp" });

    expect(mockNavigateUp).toHaveBeenCalled();
  });

  it("should call navigateDown when ArrowDown is pressed in input area", () => {
    const onSubmit = vi.fn();
    const { container } = renderWithProvider(
      <Debugger code="" onSubmit={onSubmit} />,
    );

    // Find the debugger input wrapper div (parent of CodeMirror)
    const inputWrapper =
      container.querySelector(".debugger-input")?.parentElement;
    expect(inputWrapper).toBeTruthy();

    fireEvent.keyDown(inputWrapper!, { key: "ArrowDown" });

    expect(mockNavigateDown).toHaveBeenCalled();
  });

  it("should not call navigation functions for other keys", () => {
    const onSubmit = vi.fn();
    const { container } = renderWithProvider(
      <Debugger code="" onSubmit={onSubmit} />,
    );

    const inputWrapper =
      container.querySelector(".debugger-input")?.parentElement;
    expect(inputWrapper).toBeTruthy();

    fireEvent.keyDown(inputWrapper!, { key: "ArrowLeft" });
    fireEvent.keyDown(inputWrapper!, { key: "ArrowRight" });
    fireEvent.keyDown(inputWrapper!, { key: "a" });

    expect(mockNavigateUp).not.toHaveBeenCalled();
    expect(mockNavigateDown).not.toHaveBeenCalled();
  });
});
