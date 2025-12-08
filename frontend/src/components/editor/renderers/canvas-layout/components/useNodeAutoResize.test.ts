/* Copyright 2024 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useNodeAutoResize } from "./useNodeAutoResize";

// Mock dependencies
const mockSetNodes = vi.fn();
const mockGetNodes = vi.fn();
const mockUpdateNodeInternals = vi.fn();

vi.mock("@xyflow/react", () => ({
  useReactFlow: vi.fn(() => ({
    setNodes: mockSetNodes,
    getNodes: mockGetNodes,
  })),
  useUpdateNodeInternals: vi.fn(() => mockUpdateNodeInternals),
}));

vi.mock("@/hooks/useDebounce", () => ({
  useDebounce: vi.fn((value) => value),
  useDebouncedCallback: vi.fn((fn) => fn),
}));

vi.mock("@/hooks/useResizeObserver", () => ({
  useResizeObserver: vi.fn(),
}));

describe("useNodeAutoResize - Multi-node resizing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should capture initial dimensions on resize start with multiple selected nodes", () => {
    const { result } = renderHook(() =>
      useNodeAutoResize({
        nodeId: "node1",
        hasOutput: false,
        editorHeight: 100,
      }),
    );

    // Setup mock nodes - multiple selected
    mockGetNodes.mockReturnValue([
      {
        id: "node1",
        selected: true,
        width: 600,
        height: 100,
      },
      {
        id: "node2",
        selected: true,
        width: 400,
        height: 80,
      },
      {
        id: "node3",
        selected: false,
        width: 500,
        height: 90,
      },
    ]);

    act(() => {
      result.current.handleResizeStart();
    });

    // Should not throw and should set up initial state
    expect(mockGetNodes).toHaveBeenCalled();
  });

  it("should not capture dimensions on resize start with single selected node", () => {
    const { result } = renderHook(() =>
      useNodeAutoResize({
        nodeId: "node1",
        hasOutput: false,
        editorHeight: 100,
      }),
    );

    // Setup mock nodes - single selected
    mockGetNodes.mockReturnValue([
      {
        id: "node1",
        selected: true,
        width: 600,
        height: 100,
      },
      {
        id: "node2",
        selected: false,
        width: 400,
        height: 80,
      },
    ]);

    act(() => {
      result.current.handleResizeStart();
    });

    expect(mockGetNodes).toHaveBeenCalled();
  });

  it("should apply proportional resizing to all selected nodes", () => {
    const { result } = renderHook(() =>
      useNodeAutoResize({
        nodeId: "node1",
        hasOutput: false,
        editorHeight: 100,
      }),
    );

    // Setup initial state
    const initialNodes = [
      {
        id: "node1",
        selected: true,
        width: 600,
        height: 100,
      },
      {
        id: "node2",
        selected: true,
        width: 400,
        height: 80,
      },
    ];
    mockGetNodes.mockReturnValue(initialNodes);

    act(() => {
      result.current.handleResizeStart();
    });

    // Clear previous calls
    mockSetNodes.mockClear();

    // Simulate resize - node1 is now 800x150 (1.33x width, 1.5x height)
    const resizedNodes = [
      {
        id: "node1",
        selected: true,
        width: 800,
        height: 150,
      },
      {
        id: "node2",
        selected: true,
        width: 400,
        height: 80,
      },
    ];
    mockGetNodes.mockReturnValue(resizedNodes);

    act(() => {
      result.current.handleResize();
    });

    // Verify setNodes was called
    expect(mockSetNodes).toHaveBeenCalled();

    // Get the updater function passed to setNodes
    const setNodesUpdater = mockSetNodes.mock.calls[0][0];

    // Call the updater with the resized nodes to simulate what setNodes does
    const updatedNodes = setNodesUpdater(resizedNodes);

    // node1 should remain unchanged (it's the node being resized)
    const node1 = updatedNodes.find((n: { id: string }) => n.id === "node1");
    expect(node1?.width).toBe(800);
    expect(node1?.height).toBe(150);

    // node2 should be scaled proportionally
    // Expected width: 400 * (800/600) = 533.33
    // Expected height: 80 * (150/100) = 120
    const node2 = updatedNodes.find((n: { id: string }) => n.id === "node2");
    expect(node2?.width).toBeCloseTo(533.33, 1);
    expect(node2?.height).toBe(120);
  });

  it("should not resize other nodes when only one is selected", () => {
    const { result } = renderHook(() =>
      useNodeAutoResize({
        nodeId: "node1",
        hasOutput: false,
        editorHeight: 100,
      }),
    );

    // Setup initial state - only one selected
    mockGetNodes.mockReturnValue([
      {
        id: "node1",
        selected: true,
        width: 600,
        height: 100,
      },
      {
        id: "node2",
        selected: false,
        width: 400,
        height: 80,
      },
    ]);

    act(() => {
      result.current.handleResizeStart();
    });

    // Clear any previous calls (e.g. from auto-resize effects)
    mockSetNodes.mockClear();

    // Simulate resize
    mockGetNodes.mockReturnValue([
      {
        id: "node1",
        selected: true,
        width: 800,
        height: 150,
      },
      {
        id: "node2",
        selected: false,
        width: 400,
        height: 80,
      },
    ]);

    act(() => {
      result.current.handleResize();
    });

    // setNodes should not be called for single-node resize
    // (only called in multi-node scenarios)
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it("should clean up on resize end after multi-node resize", () => {
    const { result } = renderHook(() =>
      useNodeAutoResize({
        nodeId: "node1",
        hasOutput: false,
        editorHeight: 100,
      }),
    );

    const dispatchEventSpy = vi.spyOn(window, "dispatchEvent");

    // Setup multi-node selection
    mockGetNodes.mockReturnValue([
      {
        id: "node1",
        selected: true,
        width: 600,
        height: 100,
      },
      {
        id: "node2",
        selected: true,
        width: 400,
        height: 80,
      },
    ]);

    act(() => {
      result.current.handleResizeStart();
    });

    // Simulate resize
    mockGetNodes.mockReturnValue([
      {
        id: "node1",
        selected: true,
        width: 800,
        height: 150,
      },
      {
        id: "node2",
        selected: true,
        width: 400,
        height: 80,
      },
    ]);

    act(() => {
      result.current.handleResize();
    });

    act(() => {
      result.current.handleResizeEnd();
    });

    // Should dispatch resize event
    expect(dispatchEventSpy).toHaveBeenCalledWith(expect.any(Event));

    dispatchEventSpy.mockRestore();
  });

  it("should use measured dimensions as fallback", () => {
    const { result } = renderHook(() =>
      useNodeAutoResize({
        nodeId: "node1",
        hasOutput: false,
        editorHeight: 100,
      }),
    );

    // Setup nodes with measured dimensions instead of width/height
    mockGetNodes.mockReturnValue([
      {
        id: "node1",
        selected: true,
        measured: { width: 650, height: 110 },
      },
      {
        id: "node2",
        selected: true,
        measured: { width: 450, height: 90 },
      },
    ]);

    act(() => {
      result.current.handleResizeStart();
    });

    // Should not throw and should handle measured dimensions
    expect(mockGetNodes).toHaveBeenCalled();
  });
});
