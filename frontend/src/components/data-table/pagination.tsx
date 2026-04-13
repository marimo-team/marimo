/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Table } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
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
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import { prettyNumber } from "@/utils/numbers";
import { PluralWord } from "@/utils/pluralize";

interface DataTablePaginationProps<TData> {
  table: Table<TData>;
  tableLoading?: boolean;
  showPageSizeSelector?: boolean;
}

export const DataTablePagination = <TData,>({
  table,
  tableLoading,
  showPageSizeSelector,
}: DataTablePaginationProps<TData>) => {
  const { locale } = useLocale();

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
  const pageSizes = [...pageSizeSet].toSorted((a, b) => a - b);

  const renderPageSizeSelector = () => {
    return (
      <div className="flex items-center text-xs whitespace-nowrap mr-1 print:hidden">
        <DropdownMenu>
          <DropdownMenuTrigger asChild={true}>
            <button
              type="button"
              className="border rounded justify-between pl-1.5 pr-0.5 h-6 text-xs items-center hover:bg-accent inline-flex gap-0.5"
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
    <div className="flex flex-col lg:flex-row items-center gap-0.5 lg:gap-1 px-2">
      <div className="order-2 lg:order-first">
        {showPageSizeSelector && renderPageSizeSelector()}
      </div>
      <div className="order-1 lg:order-last flex items-center print:hidden">
        <Tooltip content="First page">
          <Button
            size="xs"
            variant="text"
            data-testid="first-page-button"
            className="hidden h-6 w-5 p-0 lg:flex"
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
            className="h-6 w-5 p-0"
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
            className="h-6 w-5 p-0"
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
            className="hidden h-6 w-5 p-0 lg:flex"
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

const PAGE_ITEM_HEIGHT = 32;

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
  const [search, setSearch] = React.useState("");

  const filteredPages = React.useMemo(() => {
    if (search === "") {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    const result: number[] = [];
    for (let i = 1; i <= totalPages; i++) {
      if (String(i).startsWith(search)) {
        result.push(i);
      }
    }
    return result;
  }, [totalPages, search]);

  const handleSelect = (page: number) => {
    onPageChange(page - 1);
    setOpen(false);
  };

  const listHeight = Math.min(filteredPages.length * PAGE_ITEM_HEIGHT, 240);

  return (
    <Popover
      open={totalPages > 1 ? open : false}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setSearch("");
        }
      }}
    >
      <PopoverTrigger asChild={true} disabled={totalPages <= 1}>
        <button
          type="button"
          className={cn(
            "border rounded justify-between pl-1.5 pr-0.5 h-6 min-w-9 text-xs items-center inline-flex gap-0.5",
            totalPages > 1
              ? "hover:bg-accent cursor-pointer"
              : "opacity-50 cursor-default",
          )}
          data-testid="page-select"
          disabled={totalPages <= 1}
        >
          {currentPage}
          <ChevronDown className="h-3 w-3 opacity-50 mb-px" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-36 p-0" align="center" sideOffset={6}>
        <Command shouldFilter={false} value={String(currentPage)}>
          <CommandInput
            placeholder={`Page (1–${totalPages})`}
            rootClassName="px-2 h-8"
            className="text-xs h-8"
            autoFocus={true}
            icon={null}
            value={search}
            onValueChange={setSearch}
            onKeyDown={(e) => {
              // Allow navigation/editing keys, block non-numeric input
              const allowed = [
                "Backspace",
                "Delete",
                "ArrowLeft",
                "ArrowRight",
                "ArrowUp",
                "ArrowDown",
                "Tab",
                "Enter",
                "Escape",
              ];
              if (!allowed.includes(e.key) && !/^\d$/.test(e.key)) {
                e.preventDefault();
              }
            }}
          />
          <CommandList className="max-h-60 overflow-hidden">
            {filteredPages.length === 0 ? (
              <CommandEmpty className="py-2 text-center text-xs text-muted-foreground">
                No matching page
              </CommandEmpty>
            ) : (
              <VirtualizedPageList
                pages={filteredPages}
                currentPage={currentPage}
                listHeight={listHeight}
                onSelect={handleSelect}
              />
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};

const VirtualizedPageList = ({
  pages,
  currentPage,
  listHeight,
  onSelect,
}: {
  pages: number[];
  currentPage: number;
  listHeight: number;
  onSelect: (page: number) => void;
}) => {
  const parentRef = React.useRef<HTMLDivElement>(null);

  const currentIndex = pages.indexOf(currentPage);

  const virtualizer = useVirtualizer({
    count: pages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => PAGE_ITEM_HEIGHT,
    overscan: 10,
    initialOffset:
      currentIndex > 0
        ? Math.max(0, currentIndex * PAGE_ITEM_HEIGHT - listHeight / 2)
        : 0,
  });

  return (
    <div ref={parentRef} style={{ height: listHeight, overflow: "auto" }}>
      <div
        style={{
          height: virtualizer.getTotalSize(),
          width: "100%",
          position: "relative",
        }}
      >
        {virtualizer.getVirtualItems().map((virtualItem) => {
          const page = pages[virtualItem.index];
          return (
            <CommandItem
              key={page}
              value={String(page)}
              data-testid="page-option"
              aria-selected={page === currentPage}
              className={cn(
                "text-xs cursor-pointer",
                page === currentPage && "font-semibold bg-accent",
              )}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: virtualItem.size,
                transform: `translateY(${virtualItem.start}px)`,
              }}
              onSelect={() => onSelect(page)}
              onMouseDown={Events.preventFocus}
            >
              {page}
            </CommandItem>
          );
        })}
      </div>
    </div>
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
