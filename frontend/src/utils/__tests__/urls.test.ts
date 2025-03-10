/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { isUrl } from "../urls";

describe("isUrl", () => {
  it("should return true for a valid URL", () => {
    expect(isUrl("https://example.com")).toBe(true);
    expect(isUrl("curl -X GET http://example.com")).toBe(false);
  });
});
