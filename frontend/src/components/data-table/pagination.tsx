/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Table } from "@tanstack/react-table";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import React from "react";
import { useLocale } from "react-aria";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import { prettyNumber } from "@/utils/numbers";
import { PluralWord } from "@/utils/pluralize";
import type { DataTableSelection, PageRange } from "./types";

const MAX_PAGES_BEFORE_CLAMPING = 100;

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
  const { locale } = useLocale();

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
          <span>{prettyNumber(selected, locale)} selected</span>
          <Button
            size="xs"
            data-testid="select-all-button"
            variant="link"
            className="h-4 print:hidden"
            onMouseDown={Events.preventFocus}
            onClick={() => {
              if (onSelectAllRowsChange) {
                onSelectAllRowsChange(true);
              } else {
                table.toggleAllRowsSelected(true);
              }
            }}
          >
            Select all {prettyNumber(numRows, locale)}
          </Button>
        </>
      );
    }

    if (selected) {
      return (
        <>
          <span>{prettyNumber(selected, locale)} selected</span>
          <Button
            size="xs"
            data-testid="clear-selection-button"
            variant="link"
            className="h-4 print:hidden"
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

    const rowColumnCount = prettifyRowColumnCount(
      numRows,
      totalColumns,
      locale,
    );
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
      <div className="flex items-center text-xs whitespace-nowrap mr-1 print:hidden">
        <DropdownMenu>
          <DropdownMenuTrigger asChild={true}>
            <button
              type="button"
              className="border rounded justify-between pl-1.5 pr-0.5 text-xs items-center hover:bg-accent inline-flex gap-0.5"
            >
              {pageSize} / page
              <ChevronDown className="h-3 w-3 opacity-50 mb-px" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="center" sideOffset={6}>
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              Rows per page
            </DropdownMenuLabel>
            {[...pageSizes].map((size) => (
              <DropdownMenuItem
                key={size}
                className={cn(
                  "text-xs cursor-pointer",
                  size === pageSize && "font-semibold bg-accent",
                )}
                onSelect={() => table.setPageSize(size)}
                onMouseDown={Events.preventFocus}
              >
                {size}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    );
  };

  return (
    <div className="flex items-center gap-2 px-2">
      {showPageSizeSelector && renderPageSizeSelector()}
      <div className="flex items-center space-x-2 print:hidden">
        <Tooltip content="First page">
          <Button
            size="xs"
            variant="text"
            data-testid="first-page-button"
            className="hidden h-6 w-6 p-0 lg:flex"
            onClick={() => handlePageChange(() => table.setPageIndex(0))}
            onMouseDown={Events.preventFocus}
            disabled={!table.getCanPreviousPage()}
          >
            <ChevronsLeft className="h-4 w-4" />
          </Button>
        </Tooltip>
        <Tooltip content="Previous page">
          <Button
            size="xs"
            variant="text"
            data-testid="previous-page-button"
            className="h-6 w-6 p-0"
            onClick={() => handlePageChange(() => table.previousPage())}
            onMouseDown={Events.preventFocus}
            disabled={!table.getCanPreviousPage()}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </Tooltip>
        <div className="flex items-center justify-center text-xs font-medium gap-1">
          <span>Page</span>
          <PageSelector
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={(page) =>
              handlePageChange(() => table.setPageIndex(page))
            }
          />
          <span className="shrink-0">
            of {prettyNumber(totalPages, locale)}
          </span>
        </div>
        <Tooltip content="Next page">
          <Button
            size="xs"
            variant="text"
            data-testid="next-page-button"
            className="h-6 w-6 p-0"
            onClick={() => handlePageChange(() => table.nextPage())}
            onMouseDown={Events.preventFocus}
            disabled={!table.getCanNextPage()}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </Tooltip>
        <Tooltip content="Last page">
          <Button
            size="xs"
            variant="text"
            data-testid="last-page-button"
            className="hidden h-6 w-6 p-0 lg:flex"
            onClick={() =>
              handlePageChange(() =>
                table.setPageIndex(table.getPageCount() - 1),
              )
            }
            onMouseDown={Events.preventFocus}
            disabled={!table.getCanNextPage()}
          >
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </Tooltip>
      </div>
    </div>
  );
};

export const PageSelector = ({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) => {
  const [open, setOpen] = React.useState(false);
  const [jumpValue, setJumpValue] = React.useState("");
  const jumpInputId = React.useId();

  const pageRanges = React.useMemo(
    () => getPageRanges(currentPage, totalPages),
    [currentPage, totalPages],
  );

  const handleJump = () => {
    const page = Number.parseInt(jumpValue, 10);
    if (page >= 1 && page <= totalPages) {
      onPageChange(page - 1);
      setJumpValue("");
      setOpen(false);
    }
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild={true}>
        <button
          type="button"
          className="border rounded justify-between pl-1.5 pr-0.5 min-w-9 text-xs items-center hover:bg-accent inline-flex gap-0.5"
          data-testid="page-select"
        >
          {currentPage}
          <ChevronDown className="h-3 w-3 opacity-50 mb-px" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="w-36 overflow-hidden flex flex-col"
        scrollable={false}
        align="center"
        sideOffset={6}
        style={{ maxHeight: "22rem" }}
      >
        <div className="overflow-y-auto flex-1 min-h-0">
          {pageRanges.map((item) =>
            item.type === "ellipsis" ? (
              <DropdownMenuLabel
                key={item.key}
                className="text-center text-xs text-muted-foreground"
              >
                ...
              </DropdownMenuLabel>
            ) : (
              <DropdownMenuItem
                key={item.page}
                data-testid="page-option"
                className={cn(
                  "text-xs cursor-pointer",
                  item.page === currentPage && "font-semibold bg-accent",
                )}
                onSelect={() => onPageChange(item.page - 1)}
                onMouseDown={Events.preventFocus}
              >
                {item.page}
              </DropdownMenuItem>
            ),
          )}
        </div>
        {totalPages > MAX_PAGES_BEFORE_CLAMPING && (
          <>
            <DropdownMenuSeparator />
            <div
              className="px-2 pt-0.5 shrink-0"
              onKeyDown={(e) => e.stopPropagation()}
            >
              <label
                htmlFor={jumpInputId}
                className="text-xs text-muted-foreground block mb-1"
              >
                Jump to page
              </label>
              <Input
                id={jumpInputId}
                type="number"
                min={1}
                max={totalPages}
                placeholder={`1-${totalPages}`}
                value={jumpValue}
                onChange={(e) => setJumpValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleJump();
                  }
                  e.stopPropagation();
                }}
                className="h-6 text-xs"
                data-testid="page-jump-input"
              />
            </div>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export function getPageRanges(
  currentPage: number,
  totalPages: number,
): PageRange[] {
  if (totalPages <= MAX_PAGES_BEFORE_CLAMPING) {
    return range(totalPages).map((i) => ({ type: "page", page: i + 1 }));
  }

  const middle = Math.floor(totalPages / 2);

  const items: PageRange[] = [];
  const addPages = (start: number, count: number) => {
    for (let i = 0; i < count; i++) {
      items.push({ type: "page", page: start + i });
    }
  };

  addPages(1, 10);
  items.push({ type: "ellipsis", key: "e1" });

  if (currentPage > 10 && currentPage <= middle - 5) {
    items.push(
      { type: "page", page: currentPage },
      { type: "ellipsis", key: "e1b" },
    );
  }

  addPages(middle - 4, 10);
  items.push({ type: "ellipsis", key: "e2" });

  if (currentPage > middle + 5 && currentPage <= totalPages - 10) {
    items.push(
      { type: "page", page: currentPage },
      { type: "ellipsis", key: "e2b" },
    );
  }

  addPages(totalPages - 9, 10);

  return items;
}

export function prettifyRowCount(rowCount: number, locale: string): string {
  return `${prettyNumber(rowCount, locale)} ${new PluralWord("row").pluralize(rowCount)}`;
}

export const prettifyRowColumnCount = (
  numRows: number | "too_many",
  totalColumns: number,
  locale: string,
): string => {
  const rowsLabel =
    numRows === "too_many" ? "Unknown" : prettifyRowCount(numRows, locale);
  const columnsLabel = `${prettyNumber(totalColumns, locale)} ${new PluralWord("column").pluralize(totalColumns)}`;

  return [rowsLabel, columnsLabel].join(", ");
};
