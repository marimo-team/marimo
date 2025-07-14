/* Copyright 2024 Marimo. All rights reserved. */

import type { GridSelection } from "@glideapps/glide-data-grid";
import { CompactSelection, GridCellKind } from "@glideapps/glide-data-grid";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { pasteCells } from "../glide-utils";
import type { ModifiedGridColumn } from "../types";

// Mock navigator.clipboard
const mockClipboard = {
  readText: vi.fn(),
};

Object.defineProperty(navigator, "clipboard", {
  value: mockClipboard,
  writable: true,
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

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
      onAddEdits: mockOnAddEdits,
    });

    // Wait for the async operation
    await vi.waitFor(() => {
      expect(mockOnAddEdits).not.toHaveBeenCalled();
      expect(mockSetLocalData).not.toHaveBeenCalled();
    });
  });

  it("should handle whitespace-only clipboard text", async () => {
    mockClipboard.readText.mockResolvedValue("   \n\t  ");

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).not.toHaveBeenCalled();
      expect(mockSetLocalData).not.toHaveBeenCalled();
    });
  });

  it("should paste string data correctly", async () => {
    mockClipboard.readText.mockResolvedValue("David\t40\ttrue");

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
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

  it("should convert number values correctly", async () => {
    mockClipboard.readText.mockResolvedValue("Eve\t25.5\tfalse");

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "Eve" },
        { rowIdx: 0, columnId: "age", value: 25.5 },
        { rowIdx: 0, columnId: "active", value: false },
      ]);
    });
  });

  it("should handle boolean conversion with different values", async () => {
    mockClipboard.readText.mockResolvedValue("Frank\t30\t1");

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
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

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 0, columnId: "name", value: "Grace" },
        { rowIdx: 0, columnId: "active", value: false },
      ]);
    });
  });

  it("should handle multiple rows", async () => {
    mockClipboard.readText.mockResolvedValue("Hank\t40\ttrue\nIvy\t35\tfalse");

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
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

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(), // Only 3 rows
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
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

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(), // Only 3 columns
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

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(1, 1), // Start at column 1, row 1
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).toHaveBeenCalledWith([
        { rowIdx: 1, columnId: "active", value: false },
      ]);
    });
  });

  it("should handle no selection", async () => {
    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: {
        current: undefined,
        rows: CompactSelection.empty(),
        columns: CompactSelection.empty(),
      },
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).not.toHaveBeenCalled();
      expect(mockSetLocalData).not.toHaveBeenCalled();
    });
  });

  it("should handle clipboard read error", async () => {
    mockClipboard.readText.mockRejectedValue(
      new Error("Clipboard access denied"),
    );

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {
      // Do nothing
    });

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockOnAddEdits).not.toHaveBeenCalled();
      expect(mockSetLocalData).not.toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });

  it("should update local data when edits are applied", async () => {
    mockClipboard.readText.mockResolvedValue("Olivia\t28\ttrue");

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
      onAddEdits: mockOnAddEdits,
    });

    await vi.waitFor(() => {
      expect(mockSetLocalData).toHaveBeenCalled();

      // Verify the updater function is called
      const updater = mockSetLocalData.mock.calls[0][0];
      const originalData = createMockData();
      const updatedData = updater(originalData);

      expect(updatedData[0].name).toBe("Olivia");
      expect(updatedData[0].age).toBe(28);
      expect(updatedData[0].active).toBe(true);
    });
  });

  it("should handle empty rows in clipboard data", async () => {
    mockClipboard.readText.mockResolvedValue(
      "Paul\t30\ttrue\n\nRachel\t25\tfalse",
    );

    const mockSetLocalData = vi.fn();
    const mockOnAddEdits = vi.fn();

    pasteCells({
      selection: createMockSelection(0, 0),
      localData: createMockData(),
      setLocalData: mockSetLocalData,
      columns: createMockColumns(),
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
});
