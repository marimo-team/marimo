/* Copyright 2024 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import { useResizeObserver } from "../useResizeObserver";

describe("useResizeObserver", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  it("should call observe when ref is provided", () => {
    const observeSpy = vi.fn();
    globalThis.ResizeObserver = class MockedResizeObserver {
      observe = observeSpy;
      unobserve = vi.fn();
      disconnect = vi.fn();
    };

    renderHook(() =>
      useResizeObserver({
        ref: { current: document.createElement("div") },
      }),
    );

    expect(observeSpy).toHaveBeenCalledTimes(1);
  });

  it("should not call observe when ref is not provided", () => {
    const observeSpy = vi.fn();
    globalThis.ResizeObserver = class MockedResizeObserver {
      observe = observeSpy;
      unobserve = vi.fn();
      disconnect = vi.fn();
    };

    renderHook(() =>
      useResizeObserver({
        ref: { current: null },
      }),
    );

    expect(observeSpy).not.toHaveBeenCalled();
  });

  it("should not call observe when skipped", () => {
    const observeSpy = vi.fn();
    globalThis.ResizeObserver = class MockedResizeObserver {
      observe = observeSpy;
      unobserve = vi.fn();
      disconnect = vi.fn();
    };

    renderHook(() =>
      useResizeObserver({
        ref: { current: document.createElement("div") },
        skip: true,
      }),
    );

    expect(observeSpy).not.toHaveBeenCalled();
  });

  it("disconnect should be called once unmounted", () => {
    const disconnectSpy = vi.fn();
    globalThis.ResizeObserver = class MockedResizeObserver {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = disconnectSpy;
    };

    const { unmount } = renderHook(() =>
      useResizeObserver({
        ref: { current: document.createElement("div") },
      }),
    );

    unmount();

    expect(disconnectSpy).toHaveBeenCalledTimes(1);
  });
});
