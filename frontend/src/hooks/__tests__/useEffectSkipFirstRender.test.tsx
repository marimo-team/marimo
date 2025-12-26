/* Copyright 2026 Marimo. All rights reserved. */
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useEffectSkipFirstRender } from "../useEffectSkipFirstRender";

describe("useEffectSkipFirstRender", () => {
  it("should skip callback on first render", () => {
    const callback = vi.fn();
    const { rerender } = renderHook(
      ({ deps }) => useEffectSkipFirstRender(callback, deps),
      { initialProps: { deps: [1] } },
    );

    expect(callback).not.toHaveBeenCalled();

    rerender({ deps: [2] });
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it("should call callback on subsequent dependency changes", () => {
    const callback = vi.fn();
    const { rerender } = renderHook(
      ({ deps }) => useEffectSkipFirstRender(callback, deps),
      { initialProps: { deps: [1] } },
    );

    rerender({ deps: [2] });
    rerender({ deps: [3] });
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it("should not call callback if dependencies haven't changed", () => {
    const callback = vi.fn();
    const { rerender } = renderHook(
      ({ deps }) => useEffectSkipFirstRender(callback, deps),
      { initialProps: { deps: [1] } },
    );

    rerender({ deps: [1] });
    expect(callback).not.toHaveBeenCalled();
  });
});
