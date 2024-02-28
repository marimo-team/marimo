/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { prettyNumber } from "../numbers";

describe("prettyNumber", () => {
  it("should format numbers", () => {
    expect(prettyNumber(123_456_789)).toBe("123,456,789");
    expect(prettyNumber(1234.567_89)).toBe("1,234.57");
    expect(prettyNumber(0)).toBe("0");
  });
});
