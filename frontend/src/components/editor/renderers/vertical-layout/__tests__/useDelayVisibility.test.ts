/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDelayVisibility } from "../useDelayVisibility";
import * as cellsModule from "@/core/cells/cells";

describe("useDelayVisibility", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      cb(0);
      return 0;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should start with invisible state", () => {
    const { result } = renderHook(() => useDelayVisibility(5, "edit"));
    expect(result.current.invisible).toBe(true);
  });

  it("should become visible after delay", () => {
    const { result } = renderHook(() => useDelayVisibility(5, "edit"));

    expect(result.current.invisible).toBe(true);

    // Advance timers by the calculated delay (5-1)*15 = 60ms
    act(() => {
      vi.advanceTimersByTime(60);
    });

    expect(result.current.invisible).toBe(false);
  });

  it("should cap delay at 100ms for large number of cells", () => {
    const { result } = renderHook(() => useDelayVisibility(20, "edit"));

    expect(result.current.invisible).toBe(true);

    // Advance timers by 99ms (not enough)
    act(() => {
      vi.advanceTimersByTime(99);
    });
    expect(result.current.invisible).toBe(true);

    // Advance remaining 1ms to reach 100ms cap
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current.invisible).toBe(false);
  });

  it("should not focus any cell in read mode", () => {
    const focusSpy = vi.spyOn(cellsModule, "getNotebook");

    renderHook(() => useDelayVisibility(5, "read"));

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(focusSpy).not.toHaveBeenCalled();
  });

  it("should focus cell from URL if scrollTo parameter exists", () => {
    // Mock location.hash
    const originalHash = window.location.hash;
    Object.defineProperty(window, "location", {
      value: { hash: "#scrollTo=testCell" },
      writable: true,
    });

    // Mock document.querySelector
    const mockElement = document.createElement("div");
    mockElement.scrollIntoView = vi.fn();
    mockElement.focus = vi.fn();
    mockElement.dataset.cellId = "cell-123";

    const querySelectorSpy = vi
      .spyOn(document, "querySelector")
      .mockReturnValue(mockElement as unknown as HTMLElement);

    // Mock getNotebook
    const mockEditor = { focus: vi.fn() };
    vi.spyOn(cellsModule, "getNotebook").mockReturnValue({
      cellIds: { iterateTopLevelIds: [] },
      cellData: {},
      cellHandles: {
        "cell-123": { current: { editorView: mockEditor } },
      },
    } as unknown as cellsModule.NotebookState);

    renderHook(() => useDelayVisibility(5, "edit"));

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(querySelectorSpy).toHaveBeenCalledWith(
      '[data-cell-name="testCell"]',
    );
    // eslint-disable-next-line @typescript-eslint/unbound-method
    expect(mockElement.scrollIntoView).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/unbound-method
    expect(mockElement.focus).toHaveBeenCalled();
    expect(mockEditor.focus).toHaveBeenCalled();

    // Restore original hash
    Object.defineProperty(window, "location", {
      value: { hash: originalHash },
      writable: true,
    });
  });
});
