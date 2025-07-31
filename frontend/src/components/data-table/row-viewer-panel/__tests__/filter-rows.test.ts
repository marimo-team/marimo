/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { inSearchQuery } from "../row-viewer";

describe("inSearchQuery", () => {
  it("should filter rows based on column name", () => {
    const result = inSearchQuery({
      columnName: "name",
      columnValue: "John",
      searchQuery: "name",
    });
    expect(result).toBe(true);
  });

  it("should filter rows based on cell value", () => {
    const result = inSearchQuery({
      columnName: "name",
      columnValue: "John",
      searchQuery: "John",
    });
    expect(result).toBe(true);
  });

  it("should return false when no matches found", () => {
    const result = inSearchQuery({
      columnName: "name",
      columnValue: "John",
      searchQuery: "xyz",
    });
    expect(result).toBe(false);
  });

  it("should handle object values by converting them to strings", () => {
    const rowValues = {
      data: { key: "value" },
    };

    const result = inSearchQuery({
      columnName: "data",
      columnValue: rowValues,
      searchQuery: "value",
    });
    expect(result).toBe(true);
  });

  it("should be case insensitive", () => {
    const result = inSearchQuery({
      columnName: "name",
      columnValue: "John",
      searchQuery: "john",
    });
    expect(result).toBe(true);
  });

  it("should handle partial matches", () => {
    const result = inSearchQuery({
      columnName: "name",
      columnValue: "Johnathan Clark",
      searchQuery: "john",
    });
    expect(result).toBe(true);
  });

  it("should handle empty search query", () => {
    const result = inSearchQuery({
      columnName: "name",
      columnValue: "John",
      searchQuery: "",
    });
    expect(result).toBe(true);
  });

  it("should handle null values", () => {
    const result = inSearchQuery({
      columnName: "name",
      columnValue: null,
      searchQuery: "null",
    });
    expect(result).toBe(true);
  });
});
