/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { WithResponse } from "@/core/cells/types";
import type { OutputMessage } from "@/core/kernel/messages";
import { CONSOLE_CLEAR_DEBOUNCE_MS, ConsoleOutput } from "../ConsoleOutput";

SetupMocks.resizeObserver();

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
};

describe("ConsoleOutput integration", () => {
  const createOutput = (data: string, channel = "stdout"): OutputMessage => ({
    channel: channel as "stdout" | "stderr",
    mimetype: "text/plain",
    data,
    timestamp: 0,
  });

  const defaultProps = {
    cellId: cellId("cell-1"),
    cellName: "test_cell",
    consoleOutputs: [] as WithResponse<OutputMessage>[],
    stale: false,
    debuggerActive: false,
    onSubmitDebugger: () => {
      // noop
    },
  };

  it("should render console output with clickable URLs", () => {
    const props = {
      ...defaultProps,
      consoleOutputs: [
        {
          ...createOutput("Check out https://marimo.io for more info"),
          response: undefined,
        },
      ],
    };

    renderWithProvider(<ConsoleOutput {...props} />);

    const link = screen.getByRole("link", { name: "https://marimo.io" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "https://marimo.io");
  });

  it("starts expanded when defaultExpanded is true", () => {
    const props = {
      ...defaultProps,
      defaultExpanded: true,
      consoleOutputs: [
        {
          ...createOutput("console output"),
          response: undefined,
        },
      ],
    };

    renderWithProvider(<ConsoleOutput {...props} />);

    expect(
      screen.getByRole("button", { name: "Collapse output" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("console-output-area")).toHaveStyle({
      maxHeight: "none",
    });
  });
});

describe("ConsoleOutput pdb history", () => {
  const defaultProps = {
    cellId: cellId("cell-1"),
    cellName: "test_cell",
    consoleOutputs: [] as WithResponse<OutputMessage>[],
    stale: false,
    debuggerActive: false,
    onSubmitDebugger: vi.fn(),
  };

  const stdinPrompt = (
    data: string,
    response?: string,
  ): WithResponse<OutputMessage> => ({
    channel: "stdin" as const,
    mimetype: "text/plain",
    data,
    timestamp: 0,
    response,
  });

  it("should persist command history across StdInput remounts", () => {
    // Initial state: pdb prompt waiting for input
    const outputs1: WithResponse<OutputMessage>[] = [stdinPrompt("(Pdb) ")];

    const onSubmitDebugger = vi.fn();
    const { rerender } = renderWithProvider(
      <ConsoleOutput
        {...defaultProps}
        consoleOutputs={outputs1}
        onSubmitDebugger={onSubmitDebugger}
      />,
    );

    const input = screen.getByTestId("console-input");

    // Type "next" and submit
    fireEvent.change(input, { target: { value: "next" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onSubmitDebugger).toHaveBeenCalledWith("next", 0);

    // Simulate server response: old stdin gets a response, new stdin prompt appears
    const outputs2: WithResponse<OutputMessage>[] = [
      stdinPrompt("(Pdb) ", "next"),
      stdinPrompt("(Pdb) "),
    ];

    rerender(
      <TooltipProvider>
        <ConsoleOutput
          {...defaultProps}
          consoleOutputs={outputs2}
          onSubmitDebugger={onSubmitDebugger}
        />
      </TooltipProvider>,
    );

    // New StdInput mounted — press ArrowUp to recall previous command
    const newInput = screen.getByTestId("console-input");
    fireEvent.keyDown(newInput, { key: "ArrowUp" });

    expect(newInput).toHaveValue("next");
  });

  it("should navigate through multiple history entries across remounts", () => {
    const onSubmitDebugger = vi.fn();

    // First prompt
    const outputs1: WithResponse<OutputMessage>[] = [stdinPrompt("(Pdb) ")];

    const { rerender } = renderWithProvider(
      <ConsoleOutput
        {...defaultProps}
        consoleOutputs={outputs1}
        onSubmitDebugger={onSubmitDebugger}
      />,
    );

    // Submit "step"
    let input = screen.getByTestId("console-input");
    fireEvent.change(input, { target: { value: "step" } });
    fireEvent.keyDown(input, { key: "Enter" });

    // Second prompt
    const outputs2: WithResponse<OutputMessage>[] = [
      stdinPrompt("(Pdb) ", "step"),
      stdinPrompt("(Pdb) "),
    ];

    rerender(
      <TooltipProvider>
        <ConsoleOutput
          {...defaultProps}
          consoleOutputs={outputs2}
          onSubmitDebugger={onSubmitDebugger}
        />
      </TooltipProvider>,
    );

    // Submit "print(x)"
    input = screen.getByTestId("console-input");
    fireEvent.change(input, { target: { value: "print(x)" } });
    fireEvent.keyDown(input, { key: "Enter" });

    // Third prompt
    const outputs3: WithResponse<OutputMessage>[] = [
      stdinPrompt("(Pdb) ", "step"),
      stdinPrompt("(Pdb) ", "print(x)"),
      stdinPrompt("(Pdb) "),
    ];

    rerender(
      <TooltipProvider>
        <ConsoleOutput
          {...defaultProps}
          consoleOutputs={outputs3}
          onSubmitDebugger={onSubmitDebugger}
        />
      </TooltipProvider>,
    );

    // ArrowUp should show most recent command first
    input = screen.getByTestId("console-input");
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(input).toHaveValue("print(x)");

    // ArrowUp again should show older command
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(input).toHaveValue("step");

    // ArrowDown should go back to "print(x)"
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input).toHaveValue("print(x)");

    // ArrowDown again should return to empty input
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input).toHaveValue("");
  });
});

describe("ConsoleOutput debounced clearing", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const createOutput = (
    data: string,
    channel = "stdout",
  ): WithResponse<OutputMessage> => ({
    channel: channel as "stdout" | "stderr",
    mimetype: "text/plain",
    data,
    timestamp: 0,
    response: undefined,
  });

  const defaultProps = {
    cellId: cellId("cell-1"),
    cellName: "test_cell",
    consoleOutputs: [] as WithResponse<OutputMessage>[],
    stale: false,
    debuggerActive: false,
    onSubmitDebugger: vi.fn(),
  };

  it("should keep old outputs visible when cleared, then show new outputs immediately", () => {
    const outputs1 = [createOutput("hello world")];

    const { rerender } = renderWithProvider(
      <ConsoleOutput {...defaultProps} consoleOutputs={outputs1} />,
    );

    // Old output is visible
    expect(screen.getByText("hello world")).toBeInTheDocument();

    // Clear outputs (simulates cell re-run)
    rerender(
      <TooltipProvider>
        <ConsoleOutput {...defaultProps} consoleOutputs={[]} />
      </TooltipProvider>,
    );

    // Old output should still be visible during debounce period
    expect(screen.getByText("hello world")).toBeInTheDocument();

    // New outputs arrive before debounce fires
    const outputs2 = [createOutput("new output")];
    rerender(
      <TooltipProvider>
        <ConsoleOutput {...defaultProps} consoleOutputs={outputs2} />
      </TooltipProvider>,
    );

    // New output should be shown immediately
    expect(screen.getByText("new output")).toBeInTheDocument();
    expect(screen.queryByText("hello world")).not.toBeInTheDocument();
  });

  it("should clear outputs after debounce period if no new outputs arrive", () => {
    const outputs1 = [createOutput("old output")];

    const { rerender } = renderWithProvider(
      <ConsoleOutput {...defaultProps} consoleOutputs={outputs1} />,
    );

    expect(screen.getByText("old output")).toBeInTheDocument();

    // Clear outputs
    rerender(
      <TooltipProvider>
        <ConsoleOutput {...defaultProps} consoleOutputs={[]} />
      </TooltipProvider>,
    );

    // Still visible during debounce
    expect(screen.getByText("old output")).toBeInTheDocument();

    // Advance past debounce period
    act(() => {
      vi.advanceTimersByTime(CONSOLE_CLEAR_DEBOUNCE_MS + 1);
    });

    // Now the output should be cleared
    expect(screen.queryByText("old output")).not.toBeInTheDocument();
  });
});
