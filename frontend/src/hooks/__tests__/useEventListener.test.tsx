/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { renderHook } from "@testing-library/react-hooks";
import { useRef } from "react";
import { isRefObject } from "../useEventListener";

describe("isRefObject", () => {
  it("should return true for React ref objects", () => {
    const { result } = renderHook(() => useRef(null));
    expect(isRefObject(result)).toBe(true);
  });

  it("should return false for non-ref values", () => {
    expect(isRefObject(null)).toBe(false);
    expect(isRefObject(123)).toBe(false);
    expect(isRefObject(document.createElement("div"))).toBe(false);
    expect(isRefObject(document)).toBe(false);
    expect(isRefObject(window)).toBe(false);
  });

  it("should return true for objects with 'current' property", () => {
    expect(isRefObject({ current: document.createElement("div") })).toBe(true);
  });
});
