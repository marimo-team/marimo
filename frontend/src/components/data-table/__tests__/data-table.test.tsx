/* Copyright 2024 Marimo. All rights reserved. */
import type { ColumnDef, RowSelectionState } from "@tanstack/react-table";
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DataTable } from "../data-table";

interface TestData {
  id: number;
  name: string;
}

describe("DataTable", () => {
  it("should maintain selection state when remounted", () => {
    const mockOnRowSelectionChange = vi.fn();
    const testData: TestData[] = [
      { id: 1, name: "Test 1" },
      { id: 2, name: "Test 2" },
    ];

    const columns: Array<ColumnDef<TestData>> = [
      { accessorKey: "name", header: "Name" },
    ];

    const initialRowSelection: RowSelectionState = { "0": true };

    const commonProps = {
      data: testData,
      columns,
      selection: "single" as const,
      totalRows: 2,
      totalColumns: 1,
      pagination: false,
      rowSelection: initialRowSelection,
      onRowSelectionChange: mockOnRowSelectionChange,
    };

    const { rerender } = render(
      <TooltipProvider>
        <DataTable {...commonProps} />
      </TooltipProvider>,
    );

    // Verify initial selection is not cleared
    expect(mockOnRowSelectionChange).not.toHaveBeenCalledWith({});

    // Simulate remount (as would happen in accordion toggle)
    rerender(
      <TooltipProvider>
        <DataTable {...commonProps} />
      </TooltipProvider>,
    );

    // Verify selection is still not cleared after remount
    expect(mockOnRowSelectionChange).not.toHaveBeenCalledWith({});

    // Verify the rowSelection prop is maintained
    expect(commonProps.rowSelection).toEqual(initialRowSelection);
  });
});
