/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { inSearchQuery } from "../row-viewer";

describe("inSearchQuery", () => {
  it("should filter rows based on column name", () => {
    const result = inSearchQuery("name", "John", "name");
    expect(result).toBe(true);
  });

  it("should filter rows based on cell value", () => {
    const result = inSearchQuery("name", "John", "John");
    expect(result).toBe(true);
  });

  it("should return false when no matches found", () => {
    const result = inSearchQuery("name", "John", "xyz");
    expect(result).toBe(false);
  });

  it("should handle object values by converting them to strings", () => {
    const rowValues = {
      data: { key: "value" },
    };

    const result = inSearchQuery("data", rowValues, "value");
    expect(result).toBe(true);
  });

  it("should be case insensitive", () => {
    const result = inSearchQuery("name", "John", "john");
    expect(result).toBe(true);
  });

  it("should handle partial matches", () => {
    const result = inSearchQuery("name", "Johnathan Clark", "john");
    expect(result).toBe(true);
  });

  it("should handle empty search query", () => {
    const result = inSearchQuery("name", "John", "");
    expect(result).toBe(true);
  });

  it("should handle null values", () => {
    const result = inSearchQuery("name", null, "null");
    expect(result).toBe(true);
  });
});
