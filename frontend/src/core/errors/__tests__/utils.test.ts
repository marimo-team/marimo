/* Copyright 2024 Marimo. All rights reserved. */
import { describe, test, expect } from "vitest";
import { wrapInFunction } from "../utils";

describe("wrapInFunction", () => {
  test("wraps single line expression", () => {
    const input = "1 + 2";
    const expected = `def _():
    return 1 + 2
_()`;
    expect(wrapInFunction(input)).toBe(expected);
  });

  test("wraps multiline expression", () => {
    const input = `(1 +
2)`;
    const expected = `def _():
    return (1 +
    2)
_()`;
    expect(wrapInFunction(input)).toBe(expected);
  });

  test("wraps complex multiline expression", () => {
    const input = `foo(
    bar(1, 2),
    baz(3, 4)
)`;
    const expected = `def _():
    return foo(
        bar(1, 2),
        baz(3, 4)
    )
_()`;
    expect(wrapInFunction(input)).toBe(expected);
  });

  test("preserves empty lines", () => {
    const input = `x = 1

y = 2`;
    const expected = `def _():
    x = 1

    y = 2
    return
_()`;
    expect(wrapInFunction(input)).toBe(expected);
  });

  test("handles code with existing indentation", () => {
    const input = `if True:
    x = 1
    y = 2`;
    const expected = `def _():
    if True:
        x = 1
        y = 2
    return
_()`;
    expect(wrapInFunction(input)).toBe(expected);
  });
});
