/* Copyright 2024 Marimo. All rights reserved. */
import { renderHook, act } from "@testing-library/react";
import { useResizeHandle } from "../useResizeHandle";
import { describe, it, expect, vi } from "vitest";

describe("useResizeHandle", () => {
  it("should initialize with correct refs and style", () => {
    const { result } = renderHook(() =>
      useResizeHandle({ startingWidth: 500, onResize: () => {} }),
    );

    expect(result.current.resizableDivRef.current).toBeNull();
    expect(result.current.handleRef.current).toBeNull();
    expect(result.current.style).toEqual({ width: "500px" });
  });

  it("should handle contentWidth starting width", () => {
    const { result } = renderHook(() =>
      useResizeHandle({ startingWidth: "contentWidth", onResize: () => {} }),
    );

    expect(result.current.style).toEqual({ width: "contentWidth" });
  });

  it.skip("should call onResize when resizing ends", () => {
    const onResize = vi.fn();
    const { result } = renderHook(() =>
      useResizeHandle({ startingWidth: 500, onResize }),
    );

    // Mock DOM elements
    const mockDiv = document.createElement("div");
    mockDiv.style.width = "500px";
    // @ts-expect-error - we're testing the ref
    result.current.resizableDivRef.current = mockDiv;

    const mockHandle = document.createElement("div");
    // @ts-expect-error - we're testing the ref
    result.current.handleRef.current = mockHandle;

    // Simulate resize
    act(() => {
      const mousedownEvent = new MouseEvent("mousedown", { clientX: 0 });
      mockHandle.dispatchEvent(mousedownEvent);

      const mousemoveEvent = new MouseEvent("mousemove", { clientX: 100 });
      document.dispatchEvent(mousemoveEvent);

      const mouseupEvent = new MouseEvent("mouseup");
      document.dispatchEvent(mouseupEvent);
    });

    expect(onResize).toHaveBeenCalledWith(600); // 500px + 100px movement
  });
});
