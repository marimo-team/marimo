/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { shouldRenderDateInUTC } from "../types";

describe("shouldRenderDateInUTC", () => {
  it("should return false when dtype is undefined", () => {
    expect(shouldRenderDateInUTC(undefined)).toBe(false);
  });

  it("should return false when dtype is not a datetime with timezone", () => {
    expect(shouldRenderDateInUTC("string")).toBe(false);
    expect(shouldRenderDateInUTC("int64")).toBe(false);
    expect(shouldRenderDateInUTC("float64")).toBe(false);
    expect(shouldRenderDateInUTC("date")).toBe(false);
    expect(shouldRenderDateInUTC("datetime")).toBe(false);
    expect(shouldRenderDateInUTC("datetime[]")).toBe(false);
  });

  it("should return true for datetime with timezone format", () => {
    expect(shouldRenderDateInUTC("datetime[ns,UTC]")).toBe(true);
    expect(shouldRenderDateInUTC("datetime[ns,US/Eastern]")).toBe(true);
    expect(shouldRenderDateInUTC("datetime[ms,Europe/London]")).toBe(true);
    expect(shouldRenderDateInUTC("datetime[s,UTC]")).toBe(true);
    expect(shouldRenderDateInUTC("datetime[s,US/Eastern]")).toBe(true);
    expect(shouldRenderDateInUTC("datetime[s,Europe/London]")).toBe(true);
    expect(shouldRenderDateInUTC("datetime[m,UTC]")).toBe(true);
    expect(shouldRenderDateInUTC("datetime[m,US/Eastern]")).toBe(true);
    expect(shouldRenderDateInUTC("datetime[m,Europe/London]")).toBe(true);
  });
});
