/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo, useEffect, useState } from "react";
import {
  ColumnDef,
  ColumnFiltersState,
  OnChangeFn,
  PaginationState,
  RowSelectionState,
  SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DataTablePagination } from "./pagination";
import { DownloadActionProps, DownloadAs } from "./download-actions";
import { cn } from "@/utils/cn";
import { SearchIcon } from "lucide-react";
import { Button } from "../ui/button";
import { useDebounce } from "@uidotdev/usehooks";
import useEvent from "react-use-event-hook";
import { Tooltip } from "../ui/tooltip";
import { Spinner } from "../icons/spinner";

interface DataTableProps<TData> extends Partial<DownloadActionProps> {
  wrapperClassName?: string;
  className?: string;
  columns: Array<ColumnDef<TData>>;
  data: TData[];
  // Sorting
  sorting?: SortingState;
  setSorting?: OnChangeFn<SortingState>;
  // Pagination
  pagination?: boolean;
  pageSize?: number;
  // Selection
  selection?: "single" | "multi" | null;
  rowSelection?: RowSelectionState;
  onRowSelectionChange?: OnChangeFn<RowSelectionState>;
  // Search
  enableSearch?: boolean;
  searchQuery?: string;
  onSearchQueryChange?: (query: string) => void;
  filters?: ColumnFiltersState;
  onFiltersChange?: OnChangeFn<ColumnFiltersState>;
  reloading?: boolean;
}

const DataTableInternal = <TData,>({
  wrapperClassName,
  className,
  columns,
  data,
  sorting,
  setSorting,
  rowSelection,
  pageSize = 10,
  downloadAs,
  pagination = false,
  onRowSelectionChange,
  enableSearch = false,
  searchQuery,
  onSearchQueryChange,
  filters,
  onFiltersChange,
  reloading,
}: DataTableProps<TData>) => {
  const [isSearchEnabled, setIsSearchEnabled] = React.useState<boolean>(false);
  const [paginationState, setPaginationState] = React.useState<PaginationState>(
    { pageSize: pageSize, pageIndex: 0 },
  );

  // If pageSize changes, reset pageSize
  useEffect(() => {
    if (paginationState.pageSize !== pageSize) {
      setPaginationState((state) => ({ ...state, pageSize: pageSize }));
    }
  }, [pageSize, paginationState.pageSize]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    // pagination
    onPaginationChange: setPaginationState,
    getPaginationRowModel: pagination ? getPaginationRowModel() : undefined,
    // sorting
    onSortingChange: setSorting,
    manualSorting: true,
    getSortedRowModel: getSortedRowModel(),
    // filtering
    manualFiltering: true,
    getFilteredRowModel: getFilteredRowModel(),
    onColumnFiltersChange: onFiltersChange,
    // selection
    onRowSelectionChange: onRowSelectionChange,
    state: {
      sorting,
      columnFilters: filters,
      pagination: pagination
        ? { ...paginationState, pageSize: pageSize }
        : { pageIndex: 0, pageSize: data.length },
      rowSelection,
    },
  });

  const renderHeader = () => {
    // Hide header if no results
    if (!table.getRowModel().rows?.length) {
      return;
    }

    return table.getHeaderGroups().map((headerGroup) => (
      <TableRow key={headerGroup.id}>
        {headerGroup.headers.map((header) => {
          return (
            <TableHead
              key={header.id}
              className="h-auto min-h-10 whitespace-nowrap align-baseline"
            >
              {header.isPlaceholder
                ? null
                : flexRender(
                    header.column.columnDef.header,
                    header.getContext(),
                  )}
            </TableHead>
          );
        })}
      </TableRow>
    ));
  };

  return (
    <div className={cn(wrapperClassName, "flex flex-col space-y-2")}>
      <div className={cn(className || "rounded-md border")}>
        {onSearchQueryChange && enableSearch && (
          <SearchBar
            value={searchQuery || ""}
            onHide={() => setIsSearchEnabled(false)}
            handleSearch={onSearchQueryChange}
            hidden={!isSearchEnabled}
            reloading={reloading}
          />
        )}
        <Table>
          <TableHeader>{renderHeader()}</TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className="whitespace-nowrap truncate max-w-[300px]"
                      title={String(cell.getValue())}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between flex-shrink-0">
        {onSearchQueryChange && enableSearch && (
          <Tooltip content="Search">
            <Button
              variant="text"
              size="xs"
              className="mb-0"
              onClick={() => setIsSearchEnabled(!isSearchEnabled)}
            >
              <SearchIcon className="w-4 h-4 text-muted-foreground" />
            </Button>
          </Tooltip>
        )}
        {pagination ? <DataTablePagination table={table} /> : <div />}
        {downloadAs && <DownloadAs downloadAs={downloadAs} />}
      </div>
    </div>
  );
};

const SearchBar = (props: {
  hidden: boolean;
  value: string;
  handleSearch: (query: string) => void;
  onHide: () => void;
  reloading?: boolean;
}) => {
  const { reloading, value, handleSearch, hidden, onHide } = props;
  const [internalValue, setInternalValue] = useState(value);
  const debouncedSearch = useDebounce(internalValue, 500);
  const onSearch = useEvent(handleSearch);
  const ref = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    onSearch(debouncedSearch);
  }, [debouncedSearch, onSearch]);

  useEffect(() => {
    if (hidden) {
      // Reset
      setInternalValue("");
    } else {
      // Focus
      ref.current?.focus();
    }
  }, [hidden]);

  return (
    <div
      className={cn(
        "flex items-center space-x-2 h-8 px-2 border-b transition-all overflow-hidden duration-300 opacity-100",
        hidden && "h-0 border-none opacity-0",
      )}
    >
      <SearchIcon className="w-4 h-4 text-muted-foreground" />
      <input
        type="text"
        ref={ref}
        className="w-full h-full border-none bg-transparent focus:outline-none text-sm"
        value={internalValue}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            onHide();
          }
        }}
        autoFocus={true}
        onChange={(e) => setInternalValue(e.target.value)}
        placeholder="Search"
      />
      {reloading && <Spinner size="small" />}
    </div>
  );
};

export const DataTable = memo(DataTableInternal) as typeof DataTableInternal;
