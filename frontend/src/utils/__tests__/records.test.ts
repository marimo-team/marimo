/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { hasFunctionProperty, isRecord } from "../records";

describe("isRecord", () => {
  it("should accept plain objects", () => {
    expect(isRecord({})).toBe(true);
    expect(isRecord({ a: 1 })).toBe(true);
  });

  it("should reject null, arrays, and primitives", () => {
    expect(isRecord(null)).toBe(false);
    expect(isRecord([])).toBe(false);
    expect(isRecord("x")).toBe(false);
    expect(isRecord(1)).toBe(false);
  });
});

describe("hasFunctionProperty", () => {
  it("should detect function properties", () => {
    expect(hasFunctionProperty({ render: () => undefined }, "render")).toBe(
      true,
    );
    expect(hasFunctionProperty({ render: 1 }, "render")).toBe(false);
  });
});
