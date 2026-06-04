/* Copyright 2026 Marimo. All rights reserved. */
import type {
  ColumnDef,
  PaginationState,
  RowSelectionState,
  SortingState,
} from "@tanstack/react-table";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DataTable } from "../data-table";

interface TestData {
  id: number;
  name: string;
}

describe("DataTable", () => {
  // Restore real timers unconditionally so a failed assertion in a
  // fake-timer test can't leak fake timers into later tests.
  afterEach(() => {
    vi.useRealTimers();
  });

  it("should maintain selection state when remounted", () => {
    const mockOnRowSelectionChange = vi.fn();
    const testData: TestData[] = [
      { id: 1, name: "Test 1" },
      { id: 2, name: "Test 2" },
    ];

    const columns: ColumnDef<TestData>[] = [
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

  it("shows the hoverTemplate text as a styled tooltip on hover", async () => {
    vi.useFakeTimers();
    interface RowData {
      id: number;
      first: string;
      last: string;
    }

    const testData: RowData[] = [{ id: 1, first: "Michael", last: "Scott" }];

    const columns: ColumnDef<RowData>[] = [
      { accessorKey: "first", header: "First" },
      { accessorKey: "last", header: "Last" },
    ];

    render(
      <TooltipProvider>
        <DataTable
          data={testData}
          columns={columns}
          selection={null}
          totalRows={1}
          totalColumns={2}
          pagination={false}
          hoverTemplate={"{{first}} {{last}}"}
        />
      </TooltipProvider>,
    );

    const rows = screen.getAllByRole("row");
    // Native title is gone; hover text now comes from the styled tooltip.
    expect(rows[1]).not.toHaveAttribute("title");

    const cell = within(rows[1]).getAllByRole("cell")[0];
    fireEvent.mouseOver(cell, { buttons: 0 });
    act(() => {
      vi.advanceTimersByTime(400);
    });

    // Radix renders the content twice (visible + a11y-hidden), so match all.
    expect(screen.getAllByText("Michael Scott").length).toBeGreaterThan(0);
  });

  it("shows per-cell hover text from cellHoverTexts on hover", () => {
    vi.useFakeTimers();
    const testData: TestData[] = [{ id: 1, name: "Test 1" }];
    const columns: ColumnDef<TestData>[] = [
      { id: "name", accessorKey: "name", header: "Name" },
    ];

    render(
      <TooltipProvider>
        <DataTable
          data={testData}
          columns={columns}
          selection={null}
          totalRows={1}
          totalColumns={1}
          pagination={false}
          cellHoverTexts={{ "0": { name: "per-cell tip" } }}
        />
      </TooltipProvider>,
    );

    const cell = within(screen.getAllByRole("row")[1]).getByRole("cell");
    fireEvent.mouseOver(cell, { buttons: 0 });
    act(() => {
      vi.advanceTimersByTime(400);
    });

    expect(screen.getAllByText("per-cell tip").length).toBeGreaterThan(0);
  });

  it("links the focused cell to the tooltip content for assistive tech", () => {
    const testData: TestData[] = [{ id: 1, name: "Test 1" }];
    const columns: ColumnDef<TestData>[] = [
      { id: "name", accessorKey: "name", header: "Name" },
    ];

    render(
      <TooltipProvider>
        <DataTable
          data={testData}
          columns={columns}
          selection={null}
          totalRows={1}
          totalColumns={1}
          pagination={false}
          cellHoverTexts={{ "0": { name: "focus tip" } }}
        />
      </TooltipProvider>,
    );

    const cell = within(screen.getAllByRole("row")[1]).getByRole("cell");
    fireEvent.focus(cell);

    const describedBy = cell.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy as string)).toHaveTextContent(
      "focus tip",
    );

    fireEvent.blur(cell);
    expect(cell).not.toHaveAttribute("aria-describedby");
  });

  it("does not virtualize small datasets without pagination", () => {
    const testData = Array.from({ length: 50 }, (_, i) => ({
      id: i,
      name: `Item ${i}`,
    }));

    const columns: ColumnDef<TestData>[] = [
      { accessorKey: "id", header: "ID" },
      { accessorKey: "name", header: "Name" },
    ];

    render(
      <TooltipProvider>
        <DataTable
          data={testData}
          columns={columns}
          selection={null}
          totalRows={50}
          totalColumns={2}
          pagination={false}
        />
      </TooltipProvider>,
    );

    // All 50 data rows + 1 header row should be in the DOM (no virtualization)
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(51);
  });

  it("virtualizes large datasets — renders fewer rows than the full dataset", () => {
    const testData = Array.from({ length: 200 }, (_, i) => ({
      id: i,
      name: `Item ${i}`,
    }));

    const columns: ColumnDef<TestData>[] = [
      { accessorKey: "id", header: "ID" },
      { accessorKey: "name", header: "Name" },
    ];

    render(
      <TooltipProvider>
        <DataTable
          data={testData}
          columns={columns}
          selection={null}
          totalRows={200}
          totalColumns={2}
          pagination={false}
        />
      </TooltipProvider>,
    );

    // In jsdom the virtualizer sees a 0-height container and renders 0 data
    // rows (no layout engine). The key assertion is that significantly fewer
    // than 200 rows are in the DOM, which catches regressions where
    // virtualization is accidentally disabled and all rows are rendered.
    const rows = screen.getAllByRole("row");
    // Subtract 1 for the header row
    const dataRows = rows.length - 1;
    expect(dataRows).toBeLessThan(200);
  });

  it("should display updated data after rerender with manual sorting and pagination", () => {
    // Simulates the bug from issue #8023:
    // When a user sorts a table, rows that moved from page 2 to page 1
    // don't visually refresh after the underlying data is updated.

    interface RowData {
      id: number;
      status: string;
      value: number;
    }

    // Initial data: 4 rows, page_size=3
    const initialData: RowData[] = [
      { id: 4, status: "pending", value: 40 },
      { id: 3, status: "pending", value: 30 },
      { id: 2, status: "pending", value: 20 },
    ];

    const columns: ColumnDef<RowData>[] = [
      { id: "id", accessorFn: (row) => row.id, header: "id" },
      { id: "status", accessorFn: (row) => row.status, header: "status" },
      { id: "value", accessorFn: (row) => row.value, header: "value" },
    ];

    // Simulate sorted state (value descending) - manual sorting means
    // data comes pre-sorted from backend
    const sorting: SortingState = [{ id: "value", desc: true }];
    const setSorting = vi.fn();

    const paginationState: PaginationState = { pageIndex: 0, pageSize: 3 };
    const setPaginationState = vi.fn();

    const commonProps = {
      columns,
      selection: null as "single" | "multi" | null,
      totalRows: 4,
      totalColumns: 3,
      pagination: true,
      manualPagination: true,
      paginationState,
      setPaginationState,
      manualSorting: true,
      sorting,
      setSorting,
    };

    const { rerender } = render(
      <TooltipProvider>
        <DataTable {...commonProps} data={initialData} />
      </TooltipProvider>,
    );

    // Verify initial data is displayed - look for "pending" in cells
    const rows = screen.getAllByRole("row");
    // Row 0 is header, rows 1-3 are data rows
    expect(rows).toHaveLength(4); // 1 header + 3 data rows
    // All rows should show "pending"
    expect(within(rows[1]).getByText("pending")).toBeTruthy();
    expect(within(rows[2]).getByText("pending")).toBeTruthy();
    expect(within(rows[3]).getByText("pending")).toBeTruthy();

    // Now simulate data update: row with id=4 is now "approved"
    // Backend returns sorted data with the update applied
    const updatedData: RowData[] = [
      { id: 4, status: "approved", value: 40 },
      { id: 3, status: "pending", value: 30 },
      { id: 2, status: "pending", value: 20 },
    ];

    // Rerender with updated data (same sorting, same pagination)
    rerender(
      <TooltipProvider>
        <DataTable {...commonProps} data={updatedData} />
      </TooltipProvider>,
    );

    // BUG: The row should show "approved" but might show stale "pending"
    const updatedRows = screen.getAllByRole("row");
    expect(updatedRows).toHaveLength(4);

    // The first data row (id=4) should now show "approved"
    expect(within(updatedRows[1]).getByText("approved")).toBeTruthy();
    // Other rows should still show "pending"
    expect(within(updatedRows[2]).getByText("pending")).toBeTruthy();
    expect(within(updatedRows[3]).getByText("pending")).toBeTruthy();
  });
});

describe("DataTable — all-hidden banner", () => {
  interface Row {
    a: number;
    b: number;
  }

  const columns: ColumnDef<Row>[] = [
    { accessorKey: "a", header: "A" },
    { accessorKey: "b", header: "B" },
  ];
  const data: Row[] = [{ a: 1, b: 2 }];

  const renderWithVisibility = (hiddenColumns: string[]) =>
    render(
      <TooltipProvider>
        <DataTable
          data={data}
          columns={columns}
          selection={null}
          totalRows={1}
          totalColumns={2}
          pagination={false}
          hiddenColumns={hiddenColumns}
        />
      </TooltipProvider>,
    );

  it("renders banner when every user column is hidden", () => {
    renderWithVisibility(["a", "b"]);
    expect(screen.getByText(/All columns are hidden/i)).toBeInTheDocument();
    expect(screen.getByText(/Unhide all/i)).toBeInTheDocument();
  });

  it("does not render the banner when at least one column is visible", () => {
    renderWithVisibility(["a"]);
    expect(screen.queryByText(/All columns are hidden/i)).toBeNull();
  });

  it("does not render the banner when no columns are hidden", () => {
    renderWithVisibility([]);
    expect(screen.queryByText(/All columns are hidden/i)).toBeNull();
  });

  it("'Unhide all' restores columns hidden via the Python kwarg", () => {
    renderWithVisibility(["a", "b"]);
    expect(screen.getByText(/All columns are hidden/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Unhide all/i));
    expect(screen.queryByText(/All columns are hidden/i)).toBeNull();
  });
});
