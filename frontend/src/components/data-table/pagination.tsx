/* Copyright 2024 Marimo. All rights reserved. */
import type { Table } from "@tanstack/react-table";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { PluralWord } from "@/utils/pluralize";
import { range } from "lodash-es";

interface DataTablePaginationProps<TData> {
  table: Table<TData>;
  selection?: "single" | "multi" | null;
  onSelectAllRowsChange?: (value: boolean) => void;
}

export const DataTablePagination = <TData,>({
  table,
  selection,
  onSelectAllRowsChange,
}: DataTablePaginationProps<TData>) => {
  const renderTotal = () => {
    const selected = Object.keys(table.getState().rowSelection).length;
    const isAllPageSelected = table.getIsAllPageRowsSelected();
    const numRows = table.getRowCount();
    const isAllSelected = selected === numRows;

    if (isAllPageSelected && !isAllSelected) {
      return (
        <>
          <span>{prettyNumber(selected)} selected</span>
          <Button
            size="xs"
            data-testid="select-all-button"
            variant="link"
            className="h-4"
            onClick={() => {
              if (onSelectAllRowsChange) {
                onSelectAllRowsChange(true);
              } else {
                table.toggleAllRowsSelected(true);
              }
            }}
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
            className="h-4"
            onClick={() => {
              if (onSelectAllRowsChange) {
                onSelectAllRowsChange(false);
              } else {
                table.toggleAllRowsSelected(false);
              }
            }}
          >
            Clear selection
          </Button>
        </>
      );
    }

    let numColumns = table.getAllColumns().length;
    // If we have a selection column, subtract one from the total columns
    if (selection != null) {
      numColumns -= 1;
    }
    const rowsLabel = `${prettyNumber(numRows)} ${new PluralWord("row").pluralize(numRows)}`;
    const columnsLabel = `${prettyNumber(numColumns)} ${new PluralWord("column").pluralize(numColumns)}`;

    return <span>{[rowsLabel, columnsLabel].join(", ")}</span>;
  };
  const currentPage = Math.min(
    table.getState().pagination.pageIndex + 1,
    table.getPageCount(),
  );
  const totalPages = table.getPageCount();

  return (
    <div className="flex flex-1 items-center justify-between px-2">
      <div className="text-sm text-muted-foreground">{renderTotal()}</div>
      <div className="flex items-end space-x-2">
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
          <PageSelector
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={(page) => table.setPageIndex(page)}
          />
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

export const PageSelector = ({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) => {
  const renderOption = (i: number) => (
    <option key={i} value={i + 1}>
      {i + 1}
    </option>
  );

  const renderEllipsis = (key: number) => (
    <option key={`__${key}__`} disabled={true} value={`__${key}__`}>
      ...
    </option>
  );

  const renderPageOptions = () => {
    /* If this is too large, this can cause the browser to hang. */
    if (totalPages <= 100) {
      return range(totalPages).map((i) => renderOption(i));
    }

    const middle = Math.floor(totalPages / 2);

    // Show the first 10 pages, the middle 10 pages, and the last 10 pages.
    const firstPages = range(10).map((i) => renderOption(i));
    const middlePages = range(10).map((i) => renderOption(middle - 5 + i));
    const lastPages = range(10).map((i) => renderOption(totalPages - 10 + i));

    const result = [
      ...firstPages,
      renderEllipsis(1),
      ...middlePages,
      renderEllipsis(2),
      ...lastPages,
    ];

    if (currentPage > 10 && currentPage <= middle - 5) {
      result.splice(
        10,
        1, // delete the first ellipsis
        renderEllipsis(1),
        renderOption(currentPage - 1),
        renderEllipsis(11),
      );
    }

    if (currentPage > middle + 5 && currentPage <= totalPages - 10) {
      result.splice(
        -11,
        1, // delete the first ellipsis
        renderEllipsis(2),
        renderOption(currentPage - 1),
        renderEllipsis(22),
      );
    }

    return result;
  };

  return (
    <select
      className="cursor-pointer border rounded"
      value={currentPage}
      data-testid="page-select"
      onChange={(e) => onPageChange(Number(e.target.value) - 1)}
    >
      {renderPageOptions()}
    </select>
  );
};
