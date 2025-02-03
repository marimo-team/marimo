/* Copyright 2024 Marimo. All rights reserved. */
import { formatElapsedTime } from "../../../../components/editor/cell/CellStatus";
import { describe, expect, test } from "vitest";

describe("formatElapsedTime", () => {
  test("formats milliseconds correctly", () => {
    expect(formatElapsedTime(500)).toBe("500ms");
    expect(formatElapsedTime(50)).toBe("50ms");
  });

  test("formats seconds correctly", () => {
    expect(formatElapsedTime(1500)).toBe("1.50s");
    expect(formatElapsedTime(2340)).toBe("2.34s");
  });

  test("formats minutes and seconds correctly", () => {
    expect(formatElapsedTime(60 * 1000)).toBe("1m0s");
    expect(formatElapsedTime(90 * 1000)).toBe("1m30s");
    expect(formatElapsedTime(89 * 1000)).toBe("1m29s");
    expect(formatElapsedTime(91 * 1000)).toBe("1m31s");
    expect(formatElapsedTime(150 * 1000)).toBe("2m30s");
    expect(formatElapsedTime(151 * 1000)).toBe("2m31s");
  });

  test("handles null input", () => {
    expect(formatElapsedTime(null)).toBe("");
  });
});
