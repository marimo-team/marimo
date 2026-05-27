/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useColumnVisibility } from "../hooks/use-column-visibility";

describe("useColumnVisibility", () => {
  it("should initialize with correct default values", () => {
    const { result } = renderHook(() => useColumnVisibility());
    expect(result.current.columnVisibility).toEqual({});
  });

  it("should seed hidden columns as { name: false }", () => {
    const { result } = renderHook(() => useColumnVisibility(["a", "b"]));
    expect(result.current.columnVisibility).toEqual({ a: false, b: false });
  });

  it("should treat empty hidden list as a no-op", () => {
    const { result } = renderHook(() => useColumnVisibility([]));
    expect(result.current.columnVisibility).toEqual({});
  });

  it("should update visibility state via setter", () => {
    const { result } = renderHook(() => useColumnVisibility(["a"]));

    act(() => {
      result.current.setColumnVisibility({ a: true, b: false });
    });

    expect(result.current.columnVisibility).toEqual({ a: true, b: false });
  });

  it("should handle functional updates", () => {
    const { result } = renderHook(() => useColumnVisibility(["a"]));

    act(() => {
      result.current.setColumnVisibility((prev) => ({ ...prev, c: false }));
    });

    expect(result.current.columnVisibility).toEqual({ a: false, c: false });
  });
});
