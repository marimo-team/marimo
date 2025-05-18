/* Copyright 2024 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { DataTable } from "../data-table";
import { describe, expect, it } from "vitest";
import { vi } from "vitest";
import type { ColumnDef } from "@tanstack/react-table";
import type { RowSelectionState } from "@tanstack/react-table";
import { TooltipProvider } from "@/components/ui/tooltip";

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
