/* Copyright 2024 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { CellId } from "@/core/cells/ids";
import * as requestsModule from "@/core/network/requests";
import * as copyModule from "@/utils/copy";
import { IslandControls } from "../IslandControls";

// Mock the dependencies
vi.mock("@/core/network/requests", () => ({
  useRequestClient: vi.fn(),
}));

vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn(),
}));

describe("IslandControls", () => {
  const mockSendRun = vi.fn();
  const mockCopyToClipboard = vi.fn();
  const mockCodeCallback = vi.fn(() => "print('test code')");
  const cellId = "test-cell-id" as CellId;

  // Helper to render with required providers
  const renderWithProviders = (component: React.ReactElement) => {
    return render(<TooltipProvider>{component}</TooltipProvider>);
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSendRun.mockResolvedValue(undefined);

    vi.spyOn(requestsModule, "useRequestClient").mockReturnValue({
      sendRun: mockSendRun,
    } as any);

    vi.spyOn(copyModule, "copyToClipboard").mockImplementation(
      mockCopyToClipboard,
    );
  });

  it("should not display when visible is false", () => {
    const { container } = renderWithProviders(
      <IslandControls
        cellId={cellId}
        codeCallback={mockCodeCallback}
        visible={false}
      />,
    );

    const controlsDiv = container.firstChild as HTMLElement;
    expect(controlsDiv).toBeDefined();
    expect(controlsDiv.style.display).toBe("none");
  });

  it("should display when visible is true", () => {
    const { container } = renderWithProviders(
      <IslandControls
        cellId={cellId}
        codeCallback={mockCodeCallback}
        visible={true}
      />,
    );

    const controlsDiv = container.firstChild as HTMLElement;
    expect(controlsDiv.style.display).toBe("flex");
  });

  it("should render copy and run buttons", () => {
    renderWithProviders(
      <IslandControls
        cellId={cellId}
        codeCallback={mockCodeCallback}
        visible={true}
      />,
    );

    // Should have 2 buttons (copy and run)
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);
  });

  it("should copy code to clipboard when copy button is clicked", async () => {
    renderWithProviders(
      <IslandControls
        cellId={cellId}
        codeCallback={mockCodeCallback}
        visible={true}
      />,
    );

    const buttons = screen.getAllByRole("button");
    const copyButton = buttons[0]; // First button is copy

    fireEvent.click(copyButton);

    expect(mockCodeCallback).toHaveBeenCalled();
    expect(mockCopyToClipboard).toHaveBeenCalledWith("print('test code')");
  });

  it("should run cell when run button is clicked", async () => {
    renderWithProviders(
      <IslandControls
        cellId={cellId}
        codeCallback={mockCodeCallback}
        visible={true}
      />,
    );

    const buttons = screen.getAllByRole("button");
    const runButton = buttons[1]; // Second button is run

    fireEvent.click(runButton);

    // Wait for async operation
    await vi.waitFor(() => {
      expect(mockCodeCallback).toHaveBeenCalled();
      expect(mockSendRun).toHaveBeenCalledWith({
        cellIds: [cellId],
        codes: ["print('test code')"],
      });
    });
  });

  it("should handle run errors gracefully", async () => {
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    mockSendRun.mockRejectedValueOnce(new Error("Run failed"));

    renderWithProviders(
      <IslandControls
        cellId={cellId}
        codeCallback={mockCodeCallback}
        visible={true}
      />,
    );

    const buttons = screen.getAllByRole("button");
    const runButton = buttons[1];

    fireEvent.click(runButton);

    // Wait for error to be logged
    await vi.waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalled();
    });

    consoleErrorSpy.mockRestore();
  });

  it("should get fresh code on each button click", async () => {
    let callCount = 0;
    const dynamicCodeCallback = vi.fn(() => `code version ${++callCount}`);

    renderWithProviders(
      <IslandControls
        cellId={cellId}
        codeCallback={dynamicCodeCallback}
        visible={true}
      />,
    );

    const buttons = screen.getAllByRole("button");
    const copyButton = buttons[0];
    const runButton = buttons[1];

    fireEvent.click(copyButton);
    expect(mockCopyToClipboard).toHaveBeenCalledWith("code version 1");

    fireEvent.click(runButton);
    await vi.waitFor(() => {
      expect(mockSendRun).toHaveBeenCalledWith({
        cellIds: [cellId],
        codes: ["code version 2"],
      });
    });

    fireEvent.click(copyButton);
    expect(mockCopyToClipboard).toHaveBeenCalledWith("code version 3");
  });
});
