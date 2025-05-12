/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { filterRows } from "../row-viewer";

describe("filterRows", () => {
  const defaultRowValues = {
    name: "John",
    age: 30,
  };

  it("should filter rows based on column name", () => {
    const result = filterRows(defaultRowValues, "name");
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("name");
  });

  it("should filter rows based on cell value", () => {
    const result = filterRows(defaultRowValues, "john");
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("name");
  });

  it("should handle object values by converting them to strings", () => {
    const rowValues = {
      data: { key: "value" },
    };

    const result = filterRows(rowValues, "value");
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("data");
  });

  it("should be case insensitive", () => {
    const rowValues = {
      Name: "John",
      AGE: 30,
    };

    const result = filterRows(rowValues, "name");
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("Name");
  });

  it("should handle partial matches", () => {
    const rowValues = {
      firstName: "John",
      lastName: "Doe",
    };

    const result = filterRows(rowValues, "name");
    expect(result).toHaveLength(2);
    expect(result.map(([name]) => name)).toEqual(["firstName", "lastName"]);
  });

  it("should return empty array when no matches found", () => {
    const result = filterRows(defaultRowValues, "xyz");
    expect(result).toHaveLength(0);
  });

  it("should handle empty search query", () => {
    const result = filterRows(defaultRowValues, "");
    expect(result).toHaveLength(2);
  });

  it("should handle null values", () => {
    const rowValues = {
      name: null,
      age: 30,
    };

    const result = filterRows(rowValues, "null");
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("name");
  });
});
