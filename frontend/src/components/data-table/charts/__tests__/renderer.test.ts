/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { stringifyUnknownValue } from "@/components/data-table/utils";

describe("renderUnknownValue", () => {
  it("should render an object as a JSON string", () => {
    expect(stringifyUnknownValue({ value: { a: 1 } })).toBe('{"a":1}');
  });

  it("should render a null value as raw string when", () => {
    expect(stringifyUnknownValue({ value: null })).toBe("null");
  });

  it("should render a null value as an empty string when specified", () => {
    expect(
      stringifyUnknownValue({ value: null, nullAsEmptyString: true }),
    ).toBe("");
  });
});
