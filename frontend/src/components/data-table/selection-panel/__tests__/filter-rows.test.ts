/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { filterRows } from "../data-selection";
import type { Cell } from "@tanstack/react-table";

describe("filterRows", () => {
  const createMockCell = (value: unknown): Cell<unknown, unknown> =>
    ({
      getValue: () => value,
      column: {
        id: "test",
        columnDef: {
          meta: {},
        },
      },
    }) as Cell<unknown, unknown>;

  it("should filter rows based on column name", () => {
    const rowValues = {
      name: createMockCell("John"),
      age: createMockCell(30),
    };

    const result = filterRows(rowValues, "name");
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("name");
  });

  it("should filter rows based on cell value", () => {
    const rowValues = {
      name: createMockCell("John"),
      age: createMockCell(30),
    };

    const result = filterRows(rowValues, "john");
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("name");
  });

  it("should handle object values by converting them to strings", () => {
    const rowValues = {
      data: createMockCell({ key: "value" }),
    };

    const result = filterRows(rowValues, "value");
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("data");
  });

  it("should be case insensitive", () => {
    const rowValues = {
      Name: createMockCell("John"),
      AGE: createMockCell(30),
    };

    const result = filterRows(rowValues, "name");
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("Name");
  });

  it("should handle partial matches", () => {
    const rowValues = {
      firstName: createMockCell("John"),
      lastName: createMockCell("Doe"),
    };

    const result = filterRows(rowValues, "name");
    expect(result).toHaveLength(2);
    expect(result.map(([name]) => name)).toEqual(["firstName", "lastName"]);
  });

  it("should return empty array when no matches found", () => {
    const rowValues = {
      name: createMockCell("John"),
      age: createMockCell(30),
    };

    const result = filterRows(rowValues, "xyz");
    expect(result).toHaveLength(0);
  });

  it("should handle empty search query", () => {
    const rowValues = {
      name: createMockCell("John"),
      age: createMockCell(30),
    };

    const result = filterRows(rowValues, "");
    expect(result).toHaveLength(2);
  });

  it("should handle null values", () => {
    const rowValues = {
      name: createMockCell(null),
      age: createMockCell(30),
    };

    const result = filterRows(rowValues, "null");
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("name");
  });
});
