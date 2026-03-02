/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Table } from "@tanstack/react-table";
import { range } from "lodash-es";
import {
  ChevronDownIcon,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import * as React from "react";
import { useLocale } from "react-aria";
import { Button } from "@/components/ui/button";
import { Events } from "@/utils/events";
import { prettyNumber } from "@/utils/numbers";
import { PluralWord } from "@/utils/pluralize";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
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

import type { PageEntry } from "./types";

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
      <div className="flex items-center gap-1 text-xs whitespace-nowrap mr-1 print:hidden">
        <Select
          value={pageSize.toString()}
          onValueChange={(value) => table.setPageSize(Number(value))}
        >
          <SelectTrigger className="w-11 h-[18px] shadow-none! !hover:shadow-none ring-0! border-border text-xs p-1">
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

      <div className="flex items-end space-x-2 print:hidden">
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
            currentPage={currentPage - 1}
            totalPages={totalPages}
            onPageChange={(page) =>
              handlePageChange(() => table.setPageIndex(page))
            }
          />
          <span className="shrink-0">
            of {prettyNumber(totalPages, locale)}
          </span>
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

export const PageSelector = ({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const [inputValue, setInputValue] = React.useState("");
  const [inputError, setInputError] = React.useState(false);
  const activeItemRef = React.useRef<HTMLDivElement>(null);

  const displayPage = currentPage + 1;
  const inputId = React.useId();

  React.useEffect(() => {
    if (isOpen && activeItemRef.current) {
      activeItemRef.current.scrollIntoView({ block: "nearest" });
    }
  }, [isOpen]);

  const buildPageEntries = (): PageEntry[] => {
    if (totalPages <= 100) {
      return range(totalPages).map((i) => ({ type: "page", index: i }));
    }

    const middle = Math.floor(totalPages / 2);

    const firstPages: PageEntry[] = range(10).map((i) => ({
      type: "page",
      index: i,
    }));
    const middlePages: PageEntry[] = range(10).map((i) => ({
      type: "page",
      index: middle - 5 + i,
    }));
    const lastPages: PageEntry[] = range(10).map((i) => ({
      type: "page",
      index: totalPages - 10 + i,
    }));

    const result: PageEntry[] = [
      ...firstPages,
      { type: "ellipsis", key: 1 },
      ...middlePages,
      { type: "ellipsis", key: 2 },
      ...lastPages,
    ];

    if (currentPage >= 10 && currentPage < middle - 5) {
      result.splice(
        10,
        1,
        { type: "ellipsis", key: 1 },
        { type: "page", index: currentPage },
        { type: "ellipsis", key: 11 },
      );
    } else if (currentPage >= middle + 5 && currentPage < totalPages - 10) {
      const secondEllipsisIdx = result.findIndex(
        (e) =>
          e.type === "ellipsis" &&
          (e as { type: "ellipsis"; key: number }).key === 2,
      );
      if (secondEllipsisIdx !== -1) {
        result.splice(
          secondEllipsisIdx,
          1,
          { type: "ellipsis", key: 2 },
          { type: "page", index: currentPage },
          { type: "ellipsis", key: 22 },
        );
      }
    }

    return result;
  };
  const handleSelect = (pageIndex: number) => {
    onPageChange(pageIndex);
    setIsOpen(false);
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      const num = Number(inputValue);
      if (Number.isInteger(num) && num >= 1 && num <= totalPages) {
        onPageChange(num - 1);
        setInputValue("");
        setInputError(false);
        setIsOpen(false);
      } else {
        setInputError(true);
      }
    }
  };
  const entries = buildPageEntries();

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger
        data-testid="page-select"
        className="flex items-center gap-1.5 px-2 py-0.5 border rounded cursor-pointer
          hover:bg-accent hover:text-accent-foreground focus:outline-none"
      >
        <span className="shrink-0">{displayPage}</span>
        <ChevronDownIcon className="h-3.5 w-3.5 shrink-0" />
      </DropdownMenuTrigger>

      <DropdownMenuContent className="w-auto max-h-72 overflow-y-auto">
        {entries.map((entry) =>
          entry.type === "ellipsis" ? (
            <div
              key={`ellipsis-${entry.key}`}
              className="px-2 py-0.5 text-sm text-muted-foreground select-none"
            >
              …
            </div>
          ) : (
            <DropdownMenuItem
              key={entry.index}
              ref={entry.index === currentPage ? activeItemRef : undefined}
              className={`text-sm cursor-pointer ${
                entry.index === currentPage ? "bg-accent font-medium" : ""
              }`}
              onClick={() => handleSelect(entry.index)}
            >
              {entry.index + 1}
            </DropdownMenuItem>
          ),
        )}

        <DropdownMenuSeparator />
        <div className="px-2 py-1.5">
          <label
            className="text-xs text-muted-foreground mb-1 block"
            htmlFor={inputId}
          >
            Jump to page
          </label>
          <input
            id={inputId}
            type="number"
            min={1}
            max={totalPages}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              setInputError(false);
            }}
            onKeyDown={(e) => {
              e.stopPropagation();
              handleInputKeyDown(e);
            }}
            placeholder={`1–${totalPages}`}
            className={`w-full text-sm px-2 py-1 border rounded bg-background
              focus:outline-none focus:ring-1 ${
                inputError
                  ? "border-destructive focus:ring-destructive"
                  : "focus:ring-ring"
              }`}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
          />
          {inputError && (
            <p className="text-xs text-destructive mt-0.5">
              Enter 1 – {totalPages}
            </p>
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
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
