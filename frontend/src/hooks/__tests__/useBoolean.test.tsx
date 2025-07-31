/* Copyright 2024 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useBoolean } from "../useBoolean";

describe("useBoolean", () => {
  it("should initialize with given value", () => {
    const { result } = renderHook(() => useBoolean(true));
    expect(result.current[0]).toBe(true);
  });

  it("should toggle value", () => {
    const { result } = renderHook(() => useBoolean(false));
    act(() => result.current[1].toggle());
    expect(result.current[0]).toBe(true);
  });

  it("should set true/false", () => {
    const { result } = renderHook(() => useBoolean(false));
    act(() => result.current[1].setTrue());
    expect(result.current[0]).toBe(true);
    act(() => result.current[1].setFalse());
    expect(result.current[0]).toBe(false);
  });

  it("should handle event.stopPropagation", () => {
    const { result } = renderHook(() => useBoolean(false));
    const mockEvent = { stopPropagation: vi.fn() };
    act(() => result.current[1].setTrue(mockEvent));
    expect(mockEvent.stopPropagation).toHaveBeenCalled();
  });
});
