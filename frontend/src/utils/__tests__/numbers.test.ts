/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  prettyNumber,
  prettyScientificNumber,
  prettyEngineeringNumber,
} from "../numbers";

describe("prettyNumber", () => {
  it("should format numbers", () => {
    expect(prettyNumber(123_456_789)).toBe("123,456,789");
    expect(prettyNumber(1234.567_89)).toBe("1,234.57");
    expect(prettyNumber(0)).toBe("0");
  });
});

describe("prettyScientificNumber", () => {
  it("should handle special cases", () => {
    expect(prettyScientificNumber(0)).toBe("0");
    expect(prettyScientificNumber(Number.NaN)).toBe("NaN");
    expect(prettyScientificNumber(Number.POSITIVE_INFINITY)).toBe("Infinity");
    expect(prettyScientificNumber(Number.NEGATIVE_INFINITY)).toBe("-Infinity");
  });

  it("should format decimals with scientific notation, ignoring integer part rounding", () => {
    const opts = { shouldRound: true };
    expect(prettyScientificNumber(123_456, opts)).toBe("123,456");
    expect(prettyScientificNumber(123_456.7, opts)).toBe("123,456.7");
    expect(prettyScientificNumber(12_345.6789, opts)).toBe("12,345.68");
    expect(prettyScientificNumber(1.2345, opts)).toBe("1.23");
    expect(prettyScientificNumber(1.000_001_234, opts)).toBe("1");
    expect(prettyScientificNumber(0.12, opts)).toBe("0.12");
    expect(prettyScientificNumber(0.1234, opts)).toBe("0.12");
    expect(prettyScientificNumber(0.000_123_4, opts)).toBe("1.2e-4");
    expect(prettyScientificNumber(-1.2345, opts)).toBe("-1.23"); // Test with negative numbers
    expect(prettyScientificNumber(-1.000_001_234, opts)).toBe("-1");
    expect(prettyScientificNumber(-0.12, opts)).toBe("-0.12");
    expect(prettyScientificNumber(-0.1234, opts)).toBe("-0.12");
    expect(prettyScientificNumber(-0.000_123_4, opts)).toBe("-1.2e-4");
  });

  it("should not round numbers when shouldRound is false", () => {
    expect(prettyScientificNumber(123_456)).toBe("123,456");
    expect(prettyScientificNumber(123_456.7)).toBe("123,456.7");
    expect(prettyScientificNumber(12_345.6789)).toBe("12,345.6789");
    expect(prettyScientificNumber(1.234_567_891_011_12)).toBe(
      "1.23456789101112",
    );
  });
});

describe("prettyEngineeringNumber", () => {
  it("should handle special cases", () => {
    expect(prettyEngineeringNumber(0)).toBe("0");
    expect(prettyEngineeringNumber(-0)).toBe("0"); // Test with negative zero
    expect(prettyEngineeringNumber(Number.NaN)).toBe("NaN");
    expect(prettyEngineeringNumber(Number.POSITIVE_INFINITY)).toBe("Infinity");
    expect(prettyEngineeringNumber(Number.NEGATIVE_INFINITY)).toBe("-Infinity");
  });

  it("should format decimals with engineering notation, ignoring integer part", () => {
    expect(prettyEngineeringNumber(123_456)).toBe("123k");
    expect(prettyEngineeringNumber(123_456.7)).toBe("123k");
    expect(prettyEngineeringNumber(12_345.6789)).toBe("12.3k");
    expect(prettyEngineeringNumber(1.2345)).toBe("1.23");
    expect(prettyEngineeringNumber(1.000_001_234)).toBe("1");
    expect(prettyEngineeringNumber(0.12)).toBe("120m");
    expect(prettyEngineeringNumber(0.1234)).toBe("123m");
    expect(prettyEngineeringNumber(0.000_123_4)).toBe("123µ");
    expect(prettyEngineeringNumber(-1.2345)).toBe("-1.23"); // Test with negative numbers
    expect(prettyEngineeringNumber(-1.000_001_234)).toBe("-1");
    expect(prettyEngineeringNumber(-0.12)).toBe("-120m");
    expect(prettyEngineeringNumber(-0.1234)).toBe("-123m");
    expect(prettyEngineeringNumber(-0.000_123_4)).toBe("-123µ");
  });
});
