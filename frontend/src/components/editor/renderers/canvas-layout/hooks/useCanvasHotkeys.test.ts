/* Copyright 2024 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useCanvasHotkeys } from "./useCanvasHotkeys";

// Mock dependencies
vi.mock("@xyflow/react", () => ({
  useNodes: vi.fn(() => [
    { id: "1", data: { cellId: "cell1" }, selected: false },
    { id: "2", data: { cellId: "cell2" }, selected: true },
  ]),
  useOnSelectionChange: vi.fn(),
  useReactFlow: vi.fn(() => ({
    setNodes: vi.fn(),
    fitView: vi.fn(),
  })),
}));

vi.mock("@/hooks/useHotkey", () => ({
  useHotkey: vi.fn(),
}));

describe("useCanvasHotkeys", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should register hotkeys when editable", () => {
    const { result } = renderHook(() => useCanvasHotkeys(true));

    expect(result.current).toHaveProperty("handleSelectAll");
    expect(result.current).toHaveProperty("handleClearSelection");
    expect(result.current).toHaveProperty("handleFitView");
  });

  it("should return selected node IDs", () => {
    const { result } = renderHook(() => useCanvasHotkeys(true));

    expect(result.current.selectedNodeIds).toEqual(["cell2"]);
  });

  it("should handle select all", () => {
    const { result } = renderHook(() => useCanvasHotkeys(true));
    const mockEvent = {
      preventDefault: vi.fn(),
    } as unknown as KeyboardEvent;

    act(() => {
      result.current.handleSelectAll(mockEvent);
    });

    expect(mockEvent.preventDefault).toHaveBeenCalled();
  });

  it("should not handle actions when not editable", () => {
    const { result } = renderHook(() => useCanvasHotkeys(false));
    const mockEvent = {
      preventDefault: vi.fn(),
    } as unknown as KeyboardEvent;

    const selectAllResult = result.current.handleSelectAll(mockEvent);
    const clearSelectionResult = result.current.handleClearSelection(mockEvent);
    const fitViewResult = result.current.handleFitView(mockEvent);

    expect(selectAllResult).toBe(false);
    expect(clearSelectionResult).toBe(false);
    expect(fitViewResult).toBe(false);
    expect(mockEvent.preventDefault).not.toHaveBeenCalled();
  });
});
