/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { clamp } from "../math";

describe("math utils", () => {
  describe("clamp", () => {
    it("should return value when within bounds", () => {
      expect(clamp(5, 0, 10)).toBe(5);
    });

    it("should return min when value is below", () => {
      expect(clamp(-5, 0, 10)).toBe(0);
    });

    it("should return max when value is above", () => {
      expect(clamp(15, 0, 10)).toBe(10);
    });

    it("should handle equal min/max bounds", () => {
      expect(clamp(5, 10, 10)).toBe(10);
    });

    it("should handle decimal values", () => {
      expect(clamp(1.5, 1, 2)).toBe(1.5);
      expect(clamp(0.5, 1, 2)).toBe(1);
      expect(clamp(2.5, 1, 2)).toBe(2);
    });
  });
});
