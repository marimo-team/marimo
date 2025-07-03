/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type { Table } from "@tanstack/react-table";
import { range } from "lodash-es";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Events } from "@/utils/events";
import { PluralWord } from "@/utils/pluralize";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import type { DataTableSelection } from "./types";

interface DataTablePaginationProps<TData> {
  table: Table<TData>;
  selection?: DataTableSelection;
  totalColumns: number;
  onSelectAllRowsChange?: (value: boolean) => void;
  tableLoading?: boolean;
  showPageSizeSelector?: boolean;
}

export const DataTablePagination = <TData,>({
  table,
  selection,
  onSelectAllRowsChange,
  totalColumns,
  tableLoading,
  showPageSizeSelector,
}: DataTablePaginationProps<TData>) => {
  const renderTotal = () => {
    const { rowSelection, cellSelection } = table.getState();
    let selected = Object.keys(rowSelection).length;
    let isAllPageSelected = table.getIsAllPageRowsSelected();
    const numRows = table.getRowCount();
    let isAllSelected = selected === numRows;

    const isCellSelection =
      selection === "single-cell" || selection === "multi-cell";
    if (isCellSelection) {
      selected = cellSelection.length;
      isAllPageSelected = false;
      isAllSelected = false;
    }

    if (isAllPageSelected && !isAllSelected) {
      return (
        <>
          <span>{prettyNumber(selected)} selected</span>
          <Button
            size="xs"
            data-testid="select-all-button"
            variant="link"
            className="h-4"
            onMouseDown={Events.preventFocus}
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
            onMouseDown={Events.preventFocus}
            onClick={() => {
              if (!isCellSelection) {
                if (onSelectAllRowsChange) {
                  onSelectAllRowsChange(false);
                } else {
                  table.toggleAllRowsSelected(false);
                }
              } else if (table.resetCellSelection) {
                table.resetCellSelection();
              }
            }}
          >
            Clear selection
          </Button>
        </>
      );
    }

    const rowColumnCount = prettifyRowColumnCount(numRows, totalColumns);
    return <span>{rowColumnCount}</span>;
  };
  const currentPage = Math.min(
    table.getState().pagination.pageIndex + 1,
    table.getPageCount(),
  );
  const totalPages = table.getPageCount();

  const pageSize = table.getState().pagination.pageSize;

  const handlePageChange = (pageChangeFn: () => void) => {
    // Frequent page changes can reset the page index, so we wait until the previous change has completed
    if (!tableLoading) {
      pageChangeFn();
    }
  };

  // Ensure unique page sizes
  const pageSizeSet = new Set([5, 10, 25, 50, 100, pageSize]);
  const pageSizes = [...pageSizeSet].sort((a, b) => a - b);

  const renderPageSizeSelector = () => {
    return (
      <div className="flex items-center gap-1 text-xs whitespace-nowrap mr-1">
        <Select
          value={pageSize.toString()}
          onValueChange={(value) => table.setPageSize(Number(value))}
        >
          <SelectTrigger className="w-11 h-[18px] !shadow-none !hover:shadow-none !ring-0 border-border text-xs p-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectLabel>Rows per page</SelectLabel>
              {[...pageSizes].map((size) => {
                const sizeStr = size.toString();
                return (
                  <SelectItem key={size} value={sizeStr}>
                    {sizeStr}
                  </SelectItem>
                );
              })}
            </SelectGroup>
          </SelectContent>
        </Select>
        <span>/ page</span>
      </div>
    );
  };

  return (
    <div className="flex flex-1 items-center justify-between px-2">
      <div className="flex items-center gap-2">
        <div className="text-sm text-muted-foreground">{renderTotal()}</div>
        {showPageSizeSelector && renderPageSizeSelector()}
      </div>

      <div className="flex items-end space-x-2">
        <Button
          size="xs"
          variant="outline"
          data-testid="first-page-button"
          className="hidden h-6 w-6 p-0 lg:flex"
          onClick={() => handlePageChange(() => table.setPageIndex(0))}
          onMouseDown={Events.preventFocus}
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
          onClick={() => handlePageChange(() => table.previousPage())}
          onMouseDown={Events.preventFocus}
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
            onPageChange={(page) =>
              handlePageChange(() => table.setPageIndex(page))
            }
          />
          <span className="flex-shrink-0">of {prettyNumber(totalPages)}</span>
        </div>
        <Button
          size="xs"
          variant="outline"
          data-testid="next-page-button"
          className="h-6 w-6 p-0"
          onClick={() => handlePageChange(() => table.nextPage())}
          onMouseDown={Events.preventFocus}
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
          onClick={() =>
            handlePageChange(() => table.setPageIndex(table.getPageCount() - 1))
          }
          onMouseDown={Events.preventFocus}
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

export function prettifyRowCount(rowCount: number): string {
  return `${prettyNumber(rowCount)} ${new PluralWord("row").pluralize(rowCount)}`;
}

export const prettifyRowColumnCount = (
  numRows: number | "too_many",
  totalColumns: number,
): string => {
  const rowsLabel =
    numRows === "too_many" ? "Unknown" : prettifyRowCount(numRows);
  const columnsLabel = `${prettyNumber(totalColumns)} ${new PluralWord("column").pluralize(totalColumns)}`;

  return [rowsLabel, columnsLabel].join(", ");
};
