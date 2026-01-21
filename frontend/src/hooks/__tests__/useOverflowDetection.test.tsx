/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { useRef } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useOverflowDetection } from "../useOverflowDetection";

// Mock ResizeObserver
const mockObserve = vi.fn();
const mockDisconnect = vi.fn();

global.ResizeObserver = class MockResizeObserver {
  callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element) {
    mockObserve(target);
    // Simulate initial observation callback
    this.callback([], this);
  }

  unobserve() {
    // noop
  }

  disconnect() {
    mockDisconnect();
  }
};

describe("useOverflowDetection", () => {
  beforeEach(() => {
    mockObserve.mockClear();
    mockDisconnect.mockClear();
  });

  it("should return false when ref is null", () => {
    const { result } = renderHook(() => {
      const ref = useRef<HTMLDivElement>(null);
      return useOverflowDetection(ref);
    });

    expect(result.current).toBe(false);
    expect(mockObserve).not.toHaveBeenCalled();
  });

  it("should observe element when ref is set", () => {
    const element = document.createElement("div");

    const { result } = renderHook(() => {
      const ref = useRef<HTMLDivElement>(element);
      return useOverflowDetection(ref);
    });

    expect(mockObserve).toHaveBeenCalledWith(element);
    expect(result.current).toBe(false); // No overflow by default
  });

  it("should not observe when enabled is false", () => {
    const element = document.createElement("div");

    renderHook(() => {
      const ref = useRef<HTMLDivElement>(element);
      return useOverflowDetection(ref, false);
    });

    expect(mockObserve).not.toHaveBeenCalled();
  });

  it("should disconnect observer on unmount", () => {
    const element = document.createElement("div");

    const { unmount } = renderHook(() => {
      const ref = useRef<HTMLDivElement>(element);
      return useOverflowDetection(ref);
    });

    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });

  it("should re-observe when enabled changes from false to true", () => {
    const element = document.createElement("div");

    const { rerender } = renderHook(
      ({ enabled }) => {
        const ref = useRef<HTMLDivElement>(element);
        return useOverflowDetection(ref, enabled);
      },
      { initialProps: { enabled: false } },
    );

    expect(mockObserve).not.toHaveBeenCalled();

    rerender({ enabled: true });
    expect(mockObserve).toHaveBeenCalledWith(element);
  });

  it("should detect overflow when scrollHeight > clientHeight", () => {
    const element = document.createElement("div");
    Object.defineProperty(element, "scrollHeight", { value: 500 });
    Object.defineProperty(element, "clientHeight", { value: 200 });

    const { result } = renderHook(() => {
      const ref = useRef<HTMLDivElement>(element);
      return useOverflowDetection(ref);
    });

    expect(result.current).toBe(true);
  });

  it("should not detect overflow when scrollHeight <= clientHeight", () => {
    const element = document.createElement("div");
    Object.defineProperty(element, "scrollHeight", { value: 100 });
    Object.defineProperty(element, "clientHeight", { value: 200 });

    const { result } = renderHook(() => {
      const ref = useRef<HTMLDivElement>(element);
      return useOverflowDetection(ref);
    });

    expect(result.current).toBe(false);
  });
});
