/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { parseInitialValue } from "../htmlUtils";

describe("htmlUtils", () => {
  it.each([false, { a: 1 }, true, 0, 1, [{ a: 1 }, { b: 2 }], "hello", ""])(
    "can parse element.dataset.initialValue",
    (initialValue) => {
      const div = document.createElement("div");
      div.dataset.initialValue = JSON.stringify(initialValue);
      expect(parseInitialValue(div)).toEqual(initialValue);
    },
  );

  it("can parse an element with no initialValue", () => {
    const div = document.createElement("div");
    expect(parseInitialValue(div)).toEqual({});
  });
});
