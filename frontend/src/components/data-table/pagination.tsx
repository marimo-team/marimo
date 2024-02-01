/* Copyright 2024 Marimo. All rights reserved. */
import { Table } from "@tanstack/react-table";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";

import { Button } from "@/components/ui/button";

interface DataTablePaginationProps<TData> {
  table: Table<TData>;
}

export const DataTablePagination = <TData,>({
  table,
}: DataTablePaginationProps<TData>) => {
  const renderTotal = () => {
    const selected = table.getSelectedRowModel().rows.length;
    const isAllSelected = table.getIsAllRowsSelected();
    const isAllPageSelected = table.getIsAllPageRowsSelected();
    const count = table.getFilteredRowModel().rows.length;

    if (isAllPageSelected && !isAllSelected) {
      return (
        <span>
          {selected} selected
          <Button
            size="xs"
            variant="link"
            onClick={() => table.toggleAllRowsSelected(true)}
          >
            Select all {count}
          </Button>
        </span>
      );
    }

    if (selected) {
      return (
        <span>
          {selected} selected
          <Button
            size="xs"
            variant="link"
            onClick={() => table.toggleAllRowsSelected(false)}
          >
            Clear selection
          </Button>
        </span>
      );
    }

    return `${count} items`;
  };

  const currentPage = Math.min(
    table.getState().pagination.pageIndex + 1,
    table.getPageCount(),
  );
  const totalPages = table.getPageCount();

  return (
    <div className="flex flex-1 items-center justify-between px-2">
      <div className="text-sm text-muted-foreground">{renderTotal()}</div>
      <div className="flex items-center space-x-2">
        <Button
          size="xs"
          variant="outline"
          className="hidden h-6 w-6 p-0 lg:flex"
          onClick={() => table.setPageIndex(0)}
          disabled={!table.getCanPreviousPage()}
        >
          <span className="sr-only">Go to first page</span>
          <ChevronsLeft className="h-4 w-4" />
        </Button>
        <Button
          size="xs"
          variant="outline"
          className="h-6 w-6 p-0"
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
        >
          <span className="sr-only">Go to previous page</span>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div className="flex items-center justify-center text-xs font-medium gap-1">
          <span>Page</span>
          <select
            className="cursor-pointer border rounded"
            value={currentPage}
            onChange={(e) => table.setPageIndex(Number(e.target.value) - 1)}
          >
            {Array.from({ length: totalPages }, (_, i) => (
              <option key={i} value={i + 1}>
                {i + 1}
              </option>
            ))}
          </select>
          <span className="flex-shrink-0">of {prettyNumber(totalPages)}</span>
        </div>
        <Button
          size="xs"
          variant="outline"
          className="h-6 w-6 p-0"
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
        >
          <span className="sr-only">Go to next page</span>
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button
          size="xs"
          variant="outline"
          className="hidden h-6 w-6 p-0 lg:flex"
          onClick={() => table.setPageIndex(table.getPageCount() - 1)}
          disabled={!table.getCanNextPage()}
        >
          <span className="sr-only">Go to last page</span>
          <ChevronsRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};

function prettyNumber(value: number): string {
  return new Intl.NumberFormat().format(value);
}
