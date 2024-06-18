/* Copyright 2024 Marimo. All rights reserved. */
import { Table } from "@tanstack/react-table";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { PluralWord } from "@/utils/pluralize";

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
    const numRows = table.getFilteredRowModel().rows.length;

    if (isAllPageSelected && !isAllSelected) {
      return (
        <>
          <span>{prettyNumber(selected)} selected</span>
          <Button
            size="xs"
            data-testid="select-all-button"
            variant="link"
            className="mb-0 h-6"
            onClick={() => table.toggleAllRowsSelected(true)}
          >
            Select all {prettyNumber(numRows)}
          </Button>
        </>
      );
    }

    if (selected) {
      return (
        <>
          <span>{prettyNumber(selected)} selected</span>
          <Button
            size="xs"
            data-testid="clear-selection-button"
            variant="link"
            className="mb-0 h-6"
            onClick={() => table.toggleAllRowsSelected(false)}
          >
            Clear selection
          </Button>
        </>
      );
    }

    return (
      <span>
        {prettyNumber(numRows)} {new PluralWord("row").pluralize(numRows)}
      </span>
    );
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
          data-testid="first-page-button"
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
          data-testid="previous-page-button"
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
            data-testid="page-select"
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
          data-testid="next-page-button"
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
          data-testid="last-page-button"
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
