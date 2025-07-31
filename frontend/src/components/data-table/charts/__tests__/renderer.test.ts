/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { renderUnknownValue } from "@/components/data-table/renderers";

describe("renderUnknownValue", () => {
  it("should render an object as a JSON string", () => {
    expect(renderUnknownValue({ value: { a: 1 } })).toBe('{"a":1}');
  });

  it("should render a null value as raw string when", () => {
    expect(renderUnknownValue({ value: null })).toBe("null");
  });

  it("should render a null value as an empty string when specified", () => {
    expect(renderUnknownValue({ value: null, nullAsEmptyString: true })).toBe(
      "",
    );
  });
});
