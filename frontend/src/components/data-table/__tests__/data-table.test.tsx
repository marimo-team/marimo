/* Copyright 2024 Marimo. All rights reserved. */
import type { ColumnDef, RowSelectionState } from "@tanstack/react-table";
import { render, screen } from "@testing-library/react";
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

  it("applies hoverTemplate to the row title using row values", () => {
    interface RowData {
      id: number;
      first: string;
      last: string;
    }

    const testData: RowData[] = [
      { id: 1, first: "Michael", last: "Scott" },
      { id: 2, first: "Jim", last: "Halpert" },
    ];

    const columns: Array<ColumnDef<RowData>> = [
      { accessorKey: "first", header: "First" },
      { accessorKey: "last", header: "Last" },
    ];

    render(
      <TooltipProvider>
        <DataTable
          data={testData}
          columns={columns}
          selection={null}
          totalRows={2}
          totalColumns={2}
          pagination={false}
          hoverTemplate={"{{first}} {{last}}"}
        />
      </TooltipProvider>,
    );

    // Grab all rows and assert title attribute computed from template
    const rows = screen.getAllByRole("row");
    // The first row is header; subsequent rows correspond to data
    expect(rows[1]).toHaveAttribute("title", "Michael Scott");
    expect(rows[2]).toHaveAttribute("title", "Jim Halpert");
  });
});
