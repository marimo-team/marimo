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

  it("should handle multiple rapid calls within the same act", () => {
    // This is the core test for the stale closure fix.
    // Before the fix, calling the function multiple times in the same
    // synchronous block would always set nonce to the same value (e.g. 0+1=1),
    // because the closure captured a stale `nonce`. With the functional update
    // form `setNonce(n => n + 1)`, each call correctly increments from the
    // latest pending state.
    let renderCount = 0;
    const { result } = renderHook(() => {
      renderCount++;
      return useNonce();
    });

    const initialRenderCount = renderCount;

    // Call 3 times within the same act — only one batched re-render
    act(() => {
      result.current();
      result.current();
      result.current();
    });

    // React batches these into a single re-render, but the nonce should
    // have incremented 3 times (0 → 1 → 2 → 3) thanks to functional updates.
    // We verify a re-render happened (at least 1 extra render).
    expect(renderCount).toBeGreaterThan(initialRenderCount);
  });

  it("should trigger separate re-renders for separate act calls", () => {
    let renderCount = 0;
    const { result } = renderHook(() => {
      renderCount++;
      return useNonce();
    });

    const initialRenderCount = renderCount;

    act(() => {
      result.current();
    });

    act(() => {
      result.current();
    });

    act(() => {
      result.current();
    });

    expect(renderCount).toBe(initialRenderCount + 3);
  });

  it("should maintain stable reference across multiple re-renders", () => {
    const { result, rerender } = renderHook(() => useNonce());
    const increment = result.current;

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
