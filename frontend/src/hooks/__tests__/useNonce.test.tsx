/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useNonce } from "../useNonce";

describe("useNonce", () => {
  it("should return a stable function reference", () => {
    const { result, rerender } = renderHook(() => useNonce());
    const firstRender = result.current;

    rerender();

    expect(result.current).toBe(firstRender);
  });

  it("should trigger re-render when called", () => {
    let renderCount = 0;
    const { result } = renderHook(() => {
      renderCount++;
      return useNonce();
    });

    const initialRenderCount = renderCount;

    act(() => {
      result.current();
    });

    expect(renderCount).toBe(initialRenderCount + 1);
  });

  it("should handle multiple rapid successive calls correctly", () => {
    let renderCount = 0;
    const { result } = renderHook(() => {
      renderCount++;
      return useNonce();
    });

    const initialRenderCount = renderCount;

    // Simulate multiple rapid calls in separate act blocks
    // This tests that the stale closure fix works correctly
    act(() => {
      result.current();
    });

    act(() => {
      result.current();
    });

    act(() => {
      result.current();
    });

    // Each call should trigger a re-render (3 calls = 3 re-renders)
    expect(renderCount).toBe(initialRenderCount + 3);
  });

  it("should maintain stable reference across multiple re-renders", () => {
    const { result, rerender } = renderHook(() => useNonce());
    const increment = result.current;

    // Force multiple re-renders
    act(() => {
      result.current();
    });

    rerender();

    act(() => {
      result.current();
    });

    rerender();

    // Function reference should remain the same throughout
    expect(result.current).toBe(increment);
  });

  it("should work correctly when called from event handlers", () => {
    let renderCount = 0;
    const { result } = renderHook(() => {
      renderCount++;
      return useNonce();
    });

    const initialRenderCount = renderCount;
    const increment = result.current;

    // Simulate being called from different event handlers
    act(() => {
      increment();
    });

    expect(renderCount).toBe(initialRenderCount + 1);

    act(() => {
      increment();
    });

    expect(renderCount).toBe(initialRenderCount + 2);
  });
});
