/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getPageIndexForRow } from "../utils";

describe("getPageIndexForRow", () => {
  it("should return null when row is on current page", () => {
    // Page 0, rows 0-9
    expect(getPageIndexForRow(0, 0, 10)).toBeNull();
    expect(getPageIndexForRow(5, 0, 10)).toBeNull();
    expect(getPageIndexForRow(9, 0, 10)).toBeNull();

    // Page 1, rows 10-19
    expect(getPageIndexForRow(10, 1, 10)).toBeNull();
    expect(getPageIndexForRow(15, 1, 10)).toBeNull();
    expect(getPageIndexForRow(19, 1, 10)).toBeNull();
  });

  it("should return new page index when row is on a different page", () => {
    // Row 15 should be on page 1 when viewing page 0
    expect(getPageIndexForRow(15, 0, 10)).toBe(1);

    // Row 5 should be on page 0 when viewing page 1
    expect(getPageIndexForRow(5, 1, 10)).toBe(0);

    // Row 25 should be on page 2 when viewing page 0
    expect(getPageIndexForRow(25, 0, 10)).toBe(2);

    // Row 0 should be on page 0 when viewing page 5
    expect(getPageIndexForRow(0, 5, 10)).toBe(0);
  });

  it("should handle different page sizes", () => {
    // Page size of 20
    expect(getPageIndexForRow(0, 0, 20)).toBeNull();
    expect(getPageIndexForRow(19, 0, 20)).toBeNull();
    expect(getPageIndexForRow(20, 0, 20)).toBe(1);
    expect(getPageIndexForRow(39, 0, 20)).toBe(1);
    expect(getPageIndexForRow(40, 0, 20)).toBe(2);

    // Page size of 5
    expect(getPageIndexForRow(0, 0, 5)).toBeNull();
    expect(getPageIndexForRow(4, 0, 5)).toBeNull();
    expect(getPageIndexForRow(5, 0, 5)).toBe(1);
    expect(getPageIndexForRow(9, 0, 5)).toBe(1);
    expect(getPageIndexForRow(10, 0, 5)).toBe(2);
  });

  it("should handle boundary cases", () => {
    // First row of next page
    expect(getPageIndexForRow(10, 0, 10)).toBe(1);

    // Last row of previous page
    expect(getPageIndexForRow(9, 1, 10)).toBe(0);

    // First row of current page
    expect(getPageIndexForRow(10, 1, 10)).toBeNull();

    // Last row of current page
    expect(getPageIndexForRow(19, 1, 10)).toBeNull();
  });

  it("should handle edge case of row 0", () => {
    expect(getPageIndexForRow(0, 0, 10)).toBeNull();
    expect(getPageIndexForRow(0, 1, 10)).toBe(0);
    expect(getPageIndexForRow(0, 5, 10)).toBe(0);
  });

  it("should handle large page numbers and row indices", () => {
    // Page 100, rows 1000-1009 (page size 10)
    expect(getPageIndexForRow(1000, 100, 10)).toBeNull();
    expect(getPageIndexForRow(1009, 100, 10)).toBeNull();
    expect(getPageIndexForRow(1010, 100, 10)).toBe(101);
    expect(getPageIndexForRow(999, 100, 10)).toBe(99);
  });
});
