/* Copyright 2024 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockDocumentModel } from "@/__mocks__/document";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { CellId } from "@/core/cells/ids";
import type { runCells } from "@/core/executions";
import { cell, document } from "@/core/notebook/document/__tests__/fixtures";
import { store } from "@/core/state/jotai";
import * as copyModule from "@/utils/copy";
import { IslandControls } from "../IslandControls";

const mockRunCells = vi.fn<typeof runCells>();

vi.mock("@/core/executions", () => ({
  runCells: (...args: Parameters<typeof runCells>) => mockRunCells(...args),
}));

vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn(),
}));

describe("IslandControls", () => {
  const mockCopyToClipboard = vi.fn();
  const mockCodeCallback = vi.fn(() => "print('test code')");
  const cellId = "test-cell-id" as CellId;
  let model: ReturnType<typeof mockDocumentModel>;

  function cellCode() {
    return store.get(model.model.documentAtom)?.cells.get(cellId)?.code;
  }

  // Helper to render with required providers
  const renderWithProviders = (component: React.ReactElement) => {
    return render(
      <Provider store={store}>
        <TooltipProvider>{component}</TooltipProvider>
      </Provider>,
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockRunCells.mockResolvedValue(undefined);
    const confirmed = document();
    model = mockDocumentModel(store, {
      ...confirmed,
      cells: new Map([[cellId, cell(cellId, "print('old')")]]),
      revision: { ...confirmed.revision, order: [cellId] },
    });

    vi.spyOn(copyModule, "copyToClipboard").mockImplementation(
      mockCopyToClipboard,
    );
  });

  afterEach(() => {
    model.stop();
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

  it("writes the editor's code to the cell and runs it through the host", async () => {
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

    await vi.waitFor(() => {
      expect(mockRunCells).toHaveBeenCalledWith(store, [cellId]);
    });
    expect(cellCode()).toBe("print('test code')");
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
      expect(mockRunCells).toHaveBeenCalledWith(store, [cellId]);
    });
    expect(cellCode()).toBe("code version 2");

    fireEvent.click(copyButton);
    expect(mockCopyToClipboard).toHaveBeenCalledWith("code version 3");
  });
});
