/* Copyright 2024 Marimo. All rights reserved. */
import { afterEach, describe, expect, it } from "vitest";
import { reorderColumnSizes, storageFn } from "../storage";

describe("Column width storage", () => {
  const { clearStorage, getColumnWidth, saveColumnWidth } = storageFn;

  afterEach(() => {
    clearStorage();
  });

  it("should set width for an existing index", () => {
    // Setup initial state
    saveColumnWidth(0, 100);
    saveColumnWidth(1, 200);

    // Test
    saveColumnWidth(0, 150);

    // Verify
    expect(getColumnWidth(0)).toBe(150);
    expect(getColumnWidth(1)).toBe(200);
  });

  it("should set width for a new index", () => {
    // Setup initial state
    saveColumnWidth(0, 100);

    // Test
    saveColumnWidth(1, 200);

    // Verify
    expect(getColumnWidth(0)).toBe(100);
    expect(getColumnWidth(1)).toBe(200);
  });

  it("should pad with contentWidth when setting width for out of bounds index", () => {
    // Setup initial state
    saveColumnWidth(0, 100);

    // Test
    saveColumnWidth(3, 300);

    // Verify
    expect(getColumnWidth(0)).toBe(100);
    expect(getColumnWidth(1)).toBe("contentWidth");
    expect(getColumnWidth(2)).toBe("contentWidth");
    expect(getColumnWidth(3)).toBe(300);
  });

  it("should handle empty initial state", () => {
    // Test
    saveColumnWidth(2, 200);

    // Verify
    expect(getColumnWidth(0)).toBe("contentWidth");
    expect(getColumnWidth(1)).toBe("contentWidth");
    expect(getColumnWidth(2)).toBe(200);
  });

  it("should update multiple columns", () => {
    // Setup initial state
    saveColumnWidth(0, 100);
    saveColumnWidth(1, 200);
    saveColumnWidth(2, 300);

    // Test
    saveColumnWidth(0, 150);
    saveColumnWidth(2, 350);

    // Verify
    expect(getColumnWidth(0)).toBe(150);
    expect(getColumnWidth(1)).toBe(200);
    expect(getColumnWidth(2)).toBe(350);
  });

  it("should set contentWidth directly", () => {
    // Setup initial state
    saveColumnWidth(0, 100);
    saveColumnWidth(1, 200);

    // Test
    saveColumnWidth(0, "contentWidth");

    // Verify
    expect(getColumnWidth(0)).toBe("contentWidth");
    expect(getColumnWidth(1)).toBe(200);
  });

  it("should maintain correct widths after reordering", () => {
    // Setup initial state with 3 columns
    saveColumnWidth(0, 100);
    saveColumnWidth(1, 200);
    saveColumnWidth(2, 300);

    // Reorder column 0 to position 2
    reorderColumnSizes(0, 2);

    // Verify the widths are in the correct order after reordering
    expect(getColumnWidth(0)).toBe(200); // Original column 1
    expect(getColumnWidth(1)).toBe(300); // Original column 2
    expect(getColumnWidth(2)).toBe(100); // Original column 0
  });
});
