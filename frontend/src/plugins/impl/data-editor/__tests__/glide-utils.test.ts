/* Copyright 2026 Marimo. All rights reserved. */

import type { GridSelection } from "@glideapps/glide-data-grid";
import { CompactSelection, GridCellKind } from "@glideapps/glide-data-grid";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { isValidCellValue, pasteCells } from "../glide-utils";
import type { ModifiedGridColumn } from "../types";

// Mock navigator.clipboard
const mockClipboard = {
  readText: vi.fn(),
};

Object.defineProperty(navigator, "clipboard", {
  value: mockClipboard,
  writable: true,
});

describe("isValidCellValue", () => {
  it("distinguishes integer and number precision", () => {
    expect(isValidCellValue("number", 3.5)).toBe(true);
    expect(isValidCellValue("number", Number.POSITIVE_INFINITY)).toBe(true);
    expect(isValidCellValue("integer", 3)).toBe(true);
    expect(isValidCellValue("integer", 3.5)).toBe(false);
    expect(isValidCellValue("integer", "9007199254740993")).toBe(true);
    expect(isValidCellValue("integer", "9007199254740993.0")).toBe(true);
    expect(isValidCellValue("integer", "9007199254740993.1")).toBe(false);
    expect(isValidCellValue("integer", "1.0000000000000001")).toBe(false);
    expect(isValidCellValue("integer", "1e-324")).toBe(false);
  });
});

describe("pasteCells", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // GridSelection expects { current?: { range: { x, y } }, rows, columns }
  const createMockSelection = (x: number, y: number): GridSelection => ({
    current: {
      cell: [x, y],
      range: { x, y, width: 1, height: 1 },
      rangeStack: [],
    },
    rows: CompactSelection.empty(),
    columns: CompactSelection.empty(),
  });

  /**
   * Name    Age   Active
   * ------- ------- -------
   * Alice   25    true
   * Bob     30    false
   * Charlie 35    true
   */
  const createMockColumns = (): ModifiedGridColumn[] => [
    {
      title: "name",
      dataType: "string",
      kind: GridCellKind.Text,
      width: 100,
      id: "name",
    },
    {
      title: "age",
      dataType: "integer",
      kind: GridCellKind.Number,
      width: 100,
      id: "age",
    },
    {
      title: "active",
      dataType: "boolean",
      kind: GridCellKind.Boolean,
      width: 100,
      id: "active",
    },
  ];

  const createMockData = () => [
    { name: "Alice", age: 25, active: true },
    { name: "Bob", age: 30, active: false },
    { name: "Charlie", age: 35, active: true },
  ];

  it("should handle empty clipboard text", async () => {
    mockClipboard.readText.mockResolvedValue("");

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    // Wait for the async operation
    await vi.waitFor(() => {
      expect(mockOnAddEdits).not.toHaveBeenCalled();
    });
  });

  it("should handle whitespace-only clipboard text", async () => {
    mockClipboard.readText.mockResolvedValue("   \n\t  ");

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).not.toHaveBeenCalled();
    });
  });

  it("should paste string data correctly", async () => {
    mockClipboard.readText.mockResolvedValue("David\t40\ttrue");

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "David" },
        { rowIdx: 0, columnId: "age", value: 40 },
        { rowIdx: 0, columnId: "active", value: true },
      ]);
    });
  });

  it("should skip fractional values for integer columns", async () => {
    mockClipboard.readText.mockResolvedValue("Eve\t25.5\tfalse");

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "Eve" },
        { rowIdx: 0, columnId: "active", value: false },
      ]);
    });
  });

  it("should handle boolean conversion with different values", async () => {
    mockClipboard.readText.mockResolvedValue("Frank\t30\t1");

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "Frank" },
        { rowIdx: 0, columnId: "age", value: 30 },
        { rowIdx: 0, columnId: "active", value: true },
      ]);
    });
  });

  it("should skip invalid number values", async () => {
    mockClipboard.readText.mockResolvedValue("Grace\tinvalid\tfalse");

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "Grace" },
        { rowIdx: 0, columnId: "active", value: false },
      ]);
    });
  });

  it("should preserve unsafe integer precision", async () => {
    mockClipboard.readText.mockResolvedValue("Grace\t9007199254740993\tfalse");

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "Grace" },
        { rowIdx: 0, columnId: "age", value: "9007199254740993" },
        { rowIdx: 0, columnId: "active", value: false },
      ]);
    });
  });

  it("should handle multiple rows", async () => {
    mockClipboard.readText.mockResolvedValue("Hank\t40\ttrue\nIvy\t35\tfalse");

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "Hank" },
        { rowIdx: 0, columnId: "age", value: 40 },
        { rowIdx: 0, columnId: "active", value: true },
        { rowIdx: 1, columnId: "name", value: "Ivy" },
        { rowIdx: 1, columnId: "age", value: 35 },
        { rowIdx: 1, columnId: "active", value: false },
      ]);
    });
  });

  it("should respect data bounds - not exceed row count", async () => {
    mockClipboard.readText.mockResolvedValue(
      "Jack\t45\ttrue\nKate\t50\tfalse\nLiam\t55\ttrue",
    );

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(), // Only 3 rows
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "Jack" },
        { rowIdx: 0, columnId: "age", value: 45 },
        { rowIdx: 0, columnId: "active", value: true },
        { rowIdx: 1, columnId: "name", value: "Kate" },
        { rowIdx: 1, columnId: "age", value: 50 },
        { rowIdx: 1, columnId: "active", value: false },
        { rowIdx: 2, columnId: "name", value: "Liam" },
        { rowIdx: 2, columnId: "age", value: 55 },
        { rowIdx: 2, columnId: "active", value: true },
      ]);
    });
  });

  it("should respect column bounds - not exceed column count", async () => {
    mockClipboard.readText.mockResolvedValue("Mia\t30\ttrue\textra");

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(), // Only 3 columns
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "Mia" },
        { rowIdx: 0, columnId: "age", value: 30 },
        { rowIdx: 0, columnId: "active", value: true },
      ]);
    });
  });

  it("should handle starting position offset", async () => {
    mockClipboard.readText.mockResolvedValue("Noah\t25\ttrue");

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(1, 1), // Start at column 1, row 1
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 1, columnId: "active", value: false },
      ]);
    });
  });

  it("should handle no selection", async () => {
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: {
        current: undefined,
        rows: CompactSelection.empty(),
        columns: CompactSelection.empty(),
      },
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).not.toHaveBeenCalled();
    });
  });

  it("should handle clipboard read error", async () => {
    mockClipboard.readText.mockRejectedValue(
      new Error("Clipboard access denied"),
    );

    const mockOnAddEdits = vi.fn();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {
      // Do nothing
    });

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).not.toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });

  it("should handle empty rows in clipboard data", async () => {
    mockClipboard.readText.mockResolvedValue(
      "Paul\t30\ttrue\n\nRachel\t25\tfalse",
    );

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: "all",
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "Paul" },
        { rowIdx: 0, columnId: "age", value: 30 },
        { rowIdx: 0, columnId: "active", value: true },
        { rowIdx: 1, columnId: "name", value: "Rachel" },
        { rowIdx: 1, columnId: "age", value: 25 },
        { rowIdx: 1, columnId: "active", value: false },
      ]);
    });
  });

  it("should handle editable columns", async () => {
    mockClipboard.readText.mockResolvedValue(
      "Olivia\t28\ttrue\nWilliams\t35\tfalse",
    );

    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      data: createMockData(),
      columns: createMockColumns(),
      editableColumns: ["age"],
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "age", value: 28 },
        { rowIdx: 1, columnId: "age", value: 35 },
      ]);
    });
  });
});
