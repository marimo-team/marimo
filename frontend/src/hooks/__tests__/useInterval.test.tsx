/* Copyright 2024 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useInterval } from "../useInterval";

describe("useInterval", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should call callback after delay", () => {
    const callback = vi.fn();
    renderHook(() =>
      useInterval(callback, { delayMs: 1000, whenVisible: false }),
    );

    expect(callback).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it("should not call callback when disabled", () => {
    const callback = vi.fn();
    renderHook(() =>
      useInterval(callback, {
        delayMs: 1000,
        whenVisible: false,
        disabled: true,
      }),
    );

    vi.advanceTimersByTime(1000);
    expect(callback).not.toHaveBeenCalled();
  });

  it("should respect visibility when whenVisible is true", () => {
    const callback = vi.fn();
    Object.defineProperty(document, "visibilityState", {
      value: "hidden",
      writable: true,
    });

    renderHook(() =>
      useInterval(callback, { delayMs: 1000, whenVisible: true }),
    );

    vi.advanceTimersByTime(1000);
    expect(callback).not.toHaveBeenCalled();

    Object.defineProperty(document, "visibilityState", { value: "visible" });
    vi.advanceTimersByTime(1000);
    expect(callback).toHaveBeenCalled();
  });

  it("should cleanup on unmount", () => {
    const callback = vi.fn();
    const { unmount } = renderHook(() =>
      useInterval(callback, { delayMs: 1000, whenVisible: false }),
    );

    unmount();
    vi.advanceTimersByTime(1000);
    expect(callback).not.toHaveBeenCalled();
  });
});
