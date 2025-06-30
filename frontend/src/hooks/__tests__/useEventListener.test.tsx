/* Copyright 2024 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { useRef } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  type HTMLElementNotDerivedFromRef,
  isRefObject,
  useEventListener,
} from "../useEventListener";

describe("isRefObject", () => {
  it("should return true for React ref objects", () => {
    const { result } = renderHook(() => useRef(null));
    expect(isRefObject(result.current)).toBe(true);
  });

  it("should return false for non-ref values", () => {
    expect(isRefObject(null)).toBe(false);
    expect(isRefObject(123)).toBe(false);
    expect(isRefObject(document.createElement("div"))).toBe(false);
    expect(isRefObject(document)).toBe(false);
    expect(isRefObject(globalThis)).toBe(false);
  });

  it("should return true for objects with 'current' property", () => {
    expect(isRefObject({ current: document.createElement("div") })).toBe(true);
  });
});

describe("useEventListener", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should attach event listener to document", () => {
    const listener = vi.fn();
    const addSpy = vi.spyOn(document, "addEventListener");
    const removeSpy = vi.spyOn(document, "removeEventListener");

    const { unmount } = renderHook(() =>
      useEventListener(document, "click", listener),
    );

    // Verify listener was attached
    expect(addSpy).toHaveBeenCalledWith(
      "click",
      expect.any(Function),
      undefined,
    );

    // Simulate click
    document.dispatchEvent(new Event("click"));
    expect(listener).toHaveBeenCalled();

    // Cleanup
    unmount();
    expect(removeSpy).toHaveBeenCalled();
  });

  it("should attach event listener to window", () => {
    const listener = vi.fn();
    const addSpy = vi.spyOn(globalThis, "addEventListener");

    renderHook(() => useEventListener(globalThis, "resize", listener));

    expect(addSpy).toHaveBeenCalledWith(
      "resize",
      expect.any(Function),
      undefined,
    );
  });

  it("should attach event listener to HTML element", () => {
    const element = document.createElement("div");
    const listener = vi.fn();
    const addSpy = vi.spyOn(element, "addEventListener");

    renderHook(() =>
      useEventListener(
        element as HTMLElementNotDerivedFromRef<HTMLDivElement>,
        "click",
        listener,
      ),
    );

    expect(addSpy).toHaveBeenCalledWith(
      "click",
      expect.any(Function),
      undefined,
    );
  });

  it("should attach event listener to ref", () => {
    const element = document.createElement("div");
    const ref = { current: element };
    const listener = vi.fn();
    const addSpy = vi.spyOn(element, "addEventListener");

    renderHook(() => useEventListener(ref, "click", listener));

    expect(addSpy).toHaveBeenCalledWith(
      "click",
      expect.any(Function),
      undefined,
    );
  });

  it("should not attach listener if target is null", () => {
    const listener = vi.fn();
    const ref = { current: null };
    const addSpy = vi.spyOn(document, "addEventListener");

    renderHook(() => useEventListener(ref, "click", listener));

    expect(addSpy).not.toHaveBeenCalled();
  });

  it("should update listener when callback changes", () => {
    const listener1 = vi.fn();
    const listener2 = vi.fn();

    const { rerender } = renderHook(
      ({ cb }) => useEventListener(document, "click", cb),
      { initialProps: { cb: listener1 } },
    );

    document.dispatchEvent(new Event("click"));
    expect(listener1).toHaveBeenCalledTimes(1);
    expect(listener2).not.toHaveBeenCalled();

    rerender({ cb: listener2 });

    document.dispatchEvent(new Event("click"));
    expect(listener1).toHaveBeenCalledTimes(1);
    expect(listener2).toHaveBeenCalledTimes(1);
  });

  it("should handle options parameter", () => {
    const listener = vi.fn();
    const options = { capture: true };
    const addSpy = vi.spyOn(document, "addEventListener");

    renderHook(() => useEventListener(document, "click", listener, options));

    expect(addSpy).toHaveBeenCalledWith("click", expect.any(Function), options);
  });
});
